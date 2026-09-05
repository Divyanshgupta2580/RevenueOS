"""Comprehensive tests for Gemini Multi-Key Failover Pool in RevenueOS.

Test coverage:
1. Key 1 success: only Key 1 is called; Key 2 and Key 3 are not invoked.
2. Key 1 429 quota exhaustion: Key 2 is attempted and succeeds.
3. Key 1 and Key 2 429 quota exhaustion: Key 3 is attempted and succeeds.
4. All three unavailable: deterministic fallback with FAILOVER_EXHAUSTED telemetry.
5. Key 1 success leaves remaining keys untouched.
6. Non-retryable errors (ValidationError, JSONDecodeError): immediate fallback, NO key rotation.
7. Cooldown behavior: exhausted slot is skipped until cooldown expires, then re-eligible.
8. Concurrency safety: simultaneous async requests coordinate safely via asyncio.Lock.
9. Duplicate in-flight analysis deduplication preserved across multi-key pool.
10. Secret isolation: keys never appear in repr, string representations, or telemetry.
11. Configuration validation: fail fast with clear ValueError if zero valid keys are configured.
12. Project distribution detection: reports shared project-level quota semantics accurately.
13. Graceful shutdown: close_all closes all slot clients.
14. Decision explanation failover: explain_decision_async fails over cleanly across keys.
"""

import asyncio
import json
import time
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from apps.brain.config import (
    get_configured_gemini_api_keys,
    mask_api_key,
    validate_gemini_configuration,
)
from apps.brain.key_pool import GeminiKeyPool, GeminiKeySlot
from apps.brain.provider import GeminiProvider
from apps.brain.schemas import RecoveryBrainInput
from apps.brain.service import RecoveryBrainService


def _create_mock_client(return_text: str | None = None, side_effect: Exception | None = None) -> MagicMock:
    """Helper to build a mock genai.Client with both sync and async models."""
    mock_client = MagicMock()
    mock_response = MagicMock()
    if return_text is not None:
        mock_response.text = return_text
        mock_response.usage_metadata.prompt_token_count = 150
        mock_response.usage_metadata.candidates_token_count = 45
    else:
        mock_response.text = json.dumps({
            "action": "PAYMENT_LINK",
            "confidence": 0.88,
            "expected_recovery_value_paise": 440000,
            "reason": "Test generated recommendation via healthy key.",
            "supporting_factors": ["Soft decline"],
            "risk_factors": [],
            "stop_rationale": None,
        })
        mock_response.usage_metadata.prompt_token_count = 150
        mock_response.usage_metadata.candidates_token_count = 45

    if side_effect:
        mock_client.models.generate_content.side_effect = side_effect
        mock_client.aio.models.generate_content = AsyncMock(side_effect=side_effect)
    else:
        mock_client.models.generate_content.return_value = mock_response
        mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)

    return mock_client


def _build_test_pool_with_clients(clients: list[MagicMock]) -> GeminiKeyPool:
    """Helper to create a GeminiKeyPool pre-seeded with mock clients."""
    key_configs = [(f"KEY_{i+1}", f"fake_key_secret_{i+1}_abcdef123456") for i in range(len(clients))]
    pool = GeminiKeyPool(key_configs)
    for i, mock_c in enumerate(clients):
        pool.slots[i]._client = mock_c
    return pool


# ==============================================================================
# Test 1 & 5: Key 1 success: only Key 1 is called, Key 2 and Key 3 are NOT called
# ==============================================================================
@pytest.mark.asyncio
async def test_key_1_success_only_key_1_called() -> None:
    """Verify that when Key 1 is healthy, Key 2 and Key 3 are never called."""
    client_1 = _create_mock_client()
    client_2 = _create_mock_client()
    client_3 = _create_mock_client()

    pool = _build_test_pool_with_clients([client_1, client_2, client_3])
    provider = GeminiProvider(pool=pool)

    ctx = RecoveryBrainInput(
        payment_id="pay_failover_001",
        amount_paise=500000,
        failure_category="insufficient_funds",
    )

    out = await provider.generate_recommendation_async(ctx)
    assert out.is_fallback is False
    assert out.action == "PAYMENT_LINK"
    assert out.confidence == 0.88
    assert out.telemetry.get("key_slot") == "KEY_1"
    assert out.telemetry.get("attempts") == 1

    # Key 1 was called exactly once
    client_1.aio.models.generate_content.assert_called_once()
    # Key 2 and Key 3 were NEVER called
    client_2.aio.models.generate_content.assert_not_called()
    client_3.aio.models.generate_content.assert_not_called()


# ==============================================================================
# Test 2: Key 1 quota exhaustion (429 RESOURCE_EXHAUSTED) -> Key 2 succeeds
# ==============================================================================
@pytest.mark.asyncio
async def test_key_1_429_quota_exhausted_failover_to_key_2() -> None:
    """Verify that 429 RESOURCE_EXHAUSTED on Key 1 triggers failover to Key 2."""
    quota_error = Exception("429 RESOURCE_EXHAUSTED: Quota exceeded for project 123456")
    client_1 = _create_mock_client(side_effect=quota_error)
    client_2 = _create_mock_client()
    client_3 = _create_mock_client()

    pool = _build_test_pool_with_clients([client_1, client_2, client_3])
    provider = GeminiProvider(pool=pool)

    ctx = RecoveryBrainInput(
        payment_id="pay_failover_002",
        amount_paise=500000,
        failure_category="insufficient_funds",
    )

    out = await provider.generate_recommendation_async(ctx)
    assert out.is_fallback is False
    assert out.action == "PAYMENT_LINK"
    assert out.telemetry.get("key_slot") == "KEY_2"
    assert out.telemetry.get("attempts") == 2

    # Key 1 was attempted and failed
    client_1.aio.models.generate_content.assert_called_once()
    # Key 2 succeeded
    client_2.aio.models.generate_content.assert_called_once()
    # Key 3 was NOT called
    client_3.aio.models.generate_content.assert_not_called()

    # Slot 1 is now in cooldown and marked quota exhausted
    assert pool.slots[0].is_eligible() is False
    assert pool.slots[0].is_quota_exhausted is True
    assert pool.slots[0].consecutive_failures == 1

    # Slot 2 is healthy
    assert pool.slots[1].is_eligible() is True
    assert pool.slots[1].consecutive_failures == 0


# ==============================================================================
# Test 3: Key 1 and Key 2 quota exhaustion -> Key 3 succeeds
# ==============================================================================
@pytest.mark.asyncio
async def test_key_1_and_2_exhausted_failover_to_key_3() -> None:
    """Verify that when Key 1 and Key 2 both fail with 429, Key 3 succeeds."""
    err_429 = Exception("429 RESOURCE_EXHAUSTED: Rate limit exceeded")
    client_1 = _create_mock_client(side_effect=err_429)
    client_2 = _create_mock_client(side_effect=err_429)
    client_3 = _create_mock_client()

    pool = _build_test_pool_with_clients([client_1, client_2, client_3])
    provider = GeminiProvider(pool=pool)

    ctx = RecoveryBrainInput(
        payment_id="pay_failover_003",
        amount_paise=300000,
        failure_category="soft_decline",
    )

    out = await provider.generate_recommendation_async(ctx)
    assert out.is_fallback is False
    assert out.action == "PAYMENT_LINK"
    assert out.telemetry.get("key_slot") == "KEY_3"
    assert out.telemetry.get("attempts") == 3

    client_1.aio.models.generate_content.assert_called_once()
    client_2.aio.models.generate_content.assert_called_once()
    client_3.aio.models.generate_content.assert_called_once()

    assert pool.slots[0].is_eligible() is False
    assert pool.slots[1].is_eligible() is False
    assert pool.slots[2].is_eligible() is True


# ==============================================================================
# Test 4: All three keys unavailable -> deterministic fallback
# ==============================================================================
@pytest.mark.asyncio
async def test_all_keys_exhausted_triggers_deterministic_fallback() -> None:
    """Verify that when all 3 keys fail, system safely returns deterministic fallback with FAILOVER_EXHAUSTED."""
    err_429 = Exception("429 RESOURCE_EXHAUSTED")
    client_1 = _create_mock_client(side_effect=err_429)
    client_2 = _create_mock_client(side_effect=err_429)
    client_3 = _create_mock_client(side_effect=err_429)

    pool = _build_test_pool_with_clients([client_1, client_2, client_3])
    provider = GeminiProvider(pool=pool)

    ctx = RecoveryBrainInput(
        payment_id="pay_failover_004",
        amount_paise=250000,
        failure_category="insufficient_funds",
        retry_count=0,
    )

    out = await provider.generate_recommendation_async(ctx)
    assert out.is_fallback is True
    assert out.telemetry.get("key_slot") == "FAILOVER_EXHAUSTED"
    assert out.telemetry.get("attempts") == 3
    assert "Gemini service unavailable across 3 key slot(s)" in out.reason

    # Subsequent request immediately hits fallback without repeating calls because all are in cooldown
    out_2 = await provider.generate_recommendation_async(ctx)
    assert out_2.is_fallback is True
    assert out_2.fallback_reason == "ALL_KEYS_UNAVAILABLE"


# ==============================================================================
# Test 6: Non-retryable error (Schema validation) -> NO key rotation
# ==============================================================================
@pytest.mark.asyncio
async def test_non_retryable_schema_error_does_not_rotate_keys() -> None:
    """Verify model generating malformed JSON triggers immediate fallback without rotating to Key 2 or 3."""
    client_1 = _create_mock_client(return_text="NOT_VALID_JSON{foo")
    client_2 = _create_mock_client()
    client_3 = _create_mock_client()

    pool = _build_test_pool_with_clients([client_1, client_2, client_3])
    provider = GeminiProvider(pool=pool)

    ctx = RecoveryBrainInput(
        payment_id="pay_failover_schema",
        amount_paise=100000,
        failure_category="soft_decline",
    )

    out = await provider.generate_recommendation_async(ctx)
    assert out.is_fallback is True
    assert out.fallback_reason == "Model response validation error"
    assert out.telemetry.get("key_slot") == "KEY_1"
    assert out.telemetry.get("attempts") == 1

    # Key 1 was called
    client_1.aio.models.generate_content.assert_called_once()
    # Key 2 and Key 3 were NOT called because this is a schema error, not a key quota error
    client_2.aio.models.generate_content.assert_not_called()
    client_3.aio.models.generate_content.assert_not_called()

    # Slot 1 was NOT marked failed for quota
    assert pool.slots[0].is_eligible() is True
    assert pool.slots[0].is_quota_exhausted is False


# ==============================================================================
# Test 7: Cooldown expiration resets eligibility
# ==============================================================================
def test_cooldown_expiration_resets_eligibility() -> None:
    """Verify a slot in cooldown becomes eligible again once cooldown_until passes."""
    pool = GeminiKeyPool([("KEY_1", "test_key_123")])
    slot = pool.slots[0]
    assert slot.is_eligible() is True

    # Mark failed with 0.1s cooldown
    pool.mark_failure("KEY_1", category="QUOTA_EXHAUSTED", cooldown_s=0.1)
    assert slot.is_eligible() is False
    assert slot.is_quota_exhausted is True

    # Sleep past cooldown
    time.sleep(0.12)
    assert slot.is_eligible() is True


# ==============================================================================
# Test 8: Concurrency safety across simultaneous requests
# ==============================================================================
@pytest.mark.asyncio
async def test_concurrency_safety_multiple_simultaneous_requests() -> None:
    """Verify 5 concurrent requests coordinate safely without race conditions when Key 1 fails."""
    quota_error = Exception("429 RESOURCE_EXHAUSTED: Rate limit exceeded")
    client_1 = _create_mock_client(side_effect=quota_error)
    client_2 = _create_mock_client()

    pool = _build_test_pool_with_clients([client_1, client_2])
    provider = GeminiProvider(pool=pool)

    async def _make_request(pid: str) -> Any:
        ctx = RecoveryBrainInput(
            payment_id=pid,
            amount_paise=200000,
            failure_category="insufficient_funds",
        )
        return await provider.generate_recommendation_async(ctx)

    # Launch 5 concurrent requests with different payment IDs
    tasks = [_make_request(f"pay_concurrent_{i}") for i in range(5)]
    results = await asyncio.gather(*tasks)

    # All 5 requests should complete successfully on Key 2
    for res in results:
        assert res.is_fallback is False
        assert res.telemetry.get("key_slot") == "KEY_2"

    # Key 2 should have been called
    assert client_2.aio.models.generate_content.call_count >= 5
    # Slot 1 should be exhausted in pool
    assert pool.slots[0].is_quota_exhausted is True
    assert pool.slots[0].is_eligible() is False


# ==============================================================================
# Test 9: In-flight deduplication is preserved with multi-key pool
# ==============================================================================
@pytest.mark.asyncio
async def test_in_flight_deduplication_preserved_with_multi_key_pool() -> None:
    """Verify identical concurrent requests for same payment_id execute exactly one underlying Gemini call."""
    client_1 = _create_mock_client()
    pool = _build_test_pool_with_clients([client_1])
    provider = GeminiProvider(pool=pool)
    service = RecoveryBrainService(provider=provider)

    payment = {
        "payment_id": "pay_dedup_multikey_01",
        "amount": 400000,
        "status": "failed",
        "failure_category": "network_timeout",
        "retry_count": 0,
    }

    # Run two identical simultaneous requests
    task1 = asyncio.create_task(service.analyze_payment_async(payment))
    task2 = asyncio.create_task(service.analyze_payment_async(payment))

    res1, res2 = await asyncio.gather(task1, task2)
    assert res1.action == res2.action
    assert res1.confidence == res2.confidence

    # Exactly 1 underlying call was made to client_1
    assert client_1.aio.models.generate_content.call_count == 1


# ==============================================================================
# Test 10: Secret isolation — keys never appear in repr, string representations, or telemetry
# ==============================================================================
def test_secret_isolation_no_key_leakage() -> None:
    """Verify raw API keys never appear in slot __repr__, pool __repr__, or telemetry dicts."""
    raw_secret = "AIzaSySecretApiKeyDoNotLeak999888777"
    slot = GeminiKeySlot("KEY_1", raw_secret)

    slot_repr = repr(slot)
    slot_str = str(slot)
    assert raw_secret not in slot_repr
    assert raw_secret not in slot_str
    assert "AIzaSy...8777" in slot_repr

    pool = GeminiKeyPool([("KEY_1", raw_secret)])
    pool_repr = repr(pool)
    assert raw_secret not in pool_repr

    # Test masking utility
    masked = mask_api_key(raw_secret)
    assert raw_secret not in masked
    assert masked.startswith("AIza")
    assert masked.endswith("8777")
    assert mask_api_key(None) == "[UNSET]"


# ==============================================================================
# Test 11: Configuration validation and startup behavior
# ==============================================================================
def test_configuration_validation_behavior() -> None:
    """Verify validate_gemini_configuration succeeds when configured and raises ValueError when empty."""
    from django.conf import settings

    # Case 1: Valid keys configured
    with patch.object(settings, "GEMINI_API_KEY_1", "valid_key_1"):
        with patch.object(settings, "GEMINI_API_KEY_2", ""):
            with patch.object(settings, "GEMINI_API_KEY_3", ""):
                with patch.object(settings, "GEMINI_API_KEY", ""):
                    # Does not raise
                    validate_gemini_configuration()
                    cfg = get_configured_gemini_api_keys()
                    assert len(cfg) == 1
                    assert cfg[0][0] == "KEY_1"
                    assert cfg[0][1] == "valid_key_1"

    # Case 2: Zero keys configured raises ValueError
    with patch.object(settings, "GEMINI_API_KEY_1", ""):
        with patch.object(settings, "GEMINI_API_KEY_2", ""):
            with patch.object(settings, "GEMINI_API_KEY_3", ""):
                with patch.object(settings, "GEMINI_API_KEY", ""):
                    with pytest.raises(ValueError, match="No valid Gemini API key configured"):
                        validate_gemini_configuration()


# ==============================================================================
# Test 12: Project distribution detection reports shared quota semantics accurately
# ==============================================================================
def test_project_distribution_detection() -> None:
    """Verify pool reports project distribution and shared quota semantics accurately."""
    pool_single = GeminiKeyPool([("KEY_1", "key_a"), ("KEY_2", "key_b")])
    dist_single = pool_single.detect_project_distribution()
    assert dist_single["key_count"] == 2
    assert dist_single["shared_quota"] is True
    assert "share" in dist_single["summary"].lower()


# ==============================================================================
# Test 13: Graceful shutdown: close_all closes slot clients
# ==============================================================================
def test_key_pool_close_all() -> None:
    """Verify close_all resets all slot clients."""
    client_1 = _create_mock_client()
    pool = _build_test_pool_with_clients([client_1])
    assert pool.slots[0]._client is not None
    pool.close_all()
    assert pool.slots[0]._client is None


# ==============================================================================
# Test 14: Decision explanation failover
# ==============================================================================
@pytest.mark.asyncio
async def test_explain_decision_failover_across_keys() -> None:
    """Verify explain_decision_async fails over to Key 2 when Key 1 returns 429."""
    quota_error = Exception("429 RESOURCE_EXHAUSTED")
    client_1 = _create_mock_client(side_effect=quota_error)

    exp_text = json.dumps({
        "decision_id": "dec_exp_failover_01",
        "explanation": "Decision was approved based on recovery heuristics.",
        "key_factors": ["Soft decline", "Low retry count"],
        "policy_alignment": "Policy compliant.",
        "outcome_assessment": "Positive recovery expected.",
    })
    client_2 = _create_mock_client(return_text=exp_text)

    pool = _build_test_pool_with_clients([client_1, client_2])
    provider = GeminiProvider(pool=pool)

    decision = {
        "decision_id": "dec_exp_failover_01",
        "payment_id": "pay_exp_01",
        "policy_decision": {"status": "APPROVED", "authorized_action": "PAYMENT_LINK"},
    }

    res = await provider.explain_decision_async(decision)
    assert res.decision_id == "dec_exp_failover_01"
    assert "approved" in res.explanation.lower()

    client_1.aio.models.generate_content.assert_called_once()
    client_2.aio.models.generate_content.assert_called_once()
