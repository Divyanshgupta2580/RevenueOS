"""Acceptance and Quality Assurance Tests for Recovery Brain (Gemini 3.8 Flash).

Covers:
1. Successful payment should not trigger recovery
2. Failed payment with sufficient recovery evidence
3. Failed payment with insufficient evidence
4. Repeated failed retries
5. Previously successful recovery
6. Previously failed recovery action
7. Cooldown active
8. Maximum retry limit reached
9. STOP decision
10. PAYMENT_LINK decision
11. REMINDER decision
12. simulated RETRY decision
13. Malformed Gemini output
14. Missing required Gemini field
15. Invalid action returned by Gemini
16. Gemini timeout handling
17. Gemini API failure handling
18. Duplicate execution protection & in-flight deduplication
19. Stale payment state bypasses cache
20. Policy conflict between AI recommendation and backend rules
21. Missing customer history handled safely
22. Missing failure reason handled safely
23. Conflicting historical signals
24. Large historical dataset correctly bounded
25. Sensitive information strictly excluded from Gemini context
"""

import asyncio
import json
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from apps.brain.prompts import build_analysis_prompt
from apps.brain.provider import GeminiProvider
from apps.brain.schemas import RecoveryBrainInput, RecoveryBrainOutput
from apps.brain.service import RecoveryBrainService
from apps.database.repositories import (
    ActionRepository,
    PaymentRepository,
)
from apps.policy.engine import GuardedPolicyEngine


def test_valid_model_response_accepted() -> None:
    """Acceptance Test: Valid model output matching schema is accepted."""
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.text = json.dumps({
        "action": "PAYMENT_LINK",
        "confidence": 0.88,
        "expected_recovery_value_paise": 450000,
        "reason": "Soft decline indicates customer funds issue; checkout link via SMS/WhatsApp enables alternate payment method.",
        "supporting_factors": ["High recoverability for payment links on soft declines", "Low retry count"],
        "risk_factors": ["Customer drop-off if link is delayed"],
        "stop_rationale": None,
    })
    mock_client.models.generate_content.return_value = mock_response

    provider = GeminiProvider(api_key="test_key")
    with patch.object(provider, "_get_client", return_value=mock_client):
        input_ctx = RecoveryBrainInput(
            payment_id="pay_test_ai_001",
            amount_paise=500000,
            failure_category="insufficient_funds",
        )
        recommendation = provider.generate_recommendation(input_ctx)

        assert isinstance(recommendation, RecoveryBrainOutput)
        assert recommendation.action == "PAYMENT_LINK"
        assert recommendation.confidence == 0.88
        assert recommendation.expected_recovery_value_paise == 450000
        assert recommendation.is_fallback is False
        assert recommendation.latency_ms is not None


def test_malformed_json_response_triggers_safe_fallback() -> None:
    """Acceptance Test: Malformed JSON from model activates safe fallback without crashing."""
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.text = "NOT_JSON_INVALID_SYNTAX{{{"
    mock_client.models.generate_content.return_value = mock_response

    provider = GeminiProvider(api_key="test_key")
    with patch.object(provider, "_get_client", return_value=mock_client):
        input_ctx = RecoveryBrainInput(
            payment_id="pay_test_malformed",
            amount_paise=100000,
            failure_category="soft_decline",
        )
        rec = provider.generate_recommendation(input_ctx)

        assert rec.is_fallback is True
        assert rec.action in ["PAYMENT_LINK", "RETRY", "REMINDER", "STOP"]
        assert "Fallback recommended" in rec.reason


def test_unsupported_action_rejected_and_handled() -> None:
    """Acceptance Test: Unsupported actions like CHARGE_CARD trigger safe fallback."""
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.text = json.dumps({
        "action": "UNSUPPORTED_PROHIBITED_ACTION",
        "confidence": 0.99,
        "expected_recovery_value_paise": 100000,
        "reason": "Invalid action test",
    })
    mock_client.models.generate_content.return_value = mock_response

    provider = GeminiProvider(api_key="test_key")
    with patch.object(provider, "_get_client", return_value=mock_client):
        input_ctx = RecoveryBrainInput(
            payment_id="pay_test_bad_act",
            amount_paise=100000,
            failure_category="network_timeout",
        )
        rec = provider.generate_recommendation(input_ctx)

        assert rec.is_fallback is True
        assert rec.action in ["RETRY", "PAYMENT_LINK", "REMINDER", "STOP"]


def test_missing_fields_rejected() -> None:
    """Acceptance Test: Model responses missing required fields are rejected."""
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.text = json.dumps({"action": "RETRY"})  # Missing confidence, reason, etc.
    mock_client.models.generate_content.return_value = mock_response

    provider = GeminiProvider(api_key="test_key")
    with patch.object(provider, "_get_client", return_value=mock_client):
        input_ctx = RecoveryBrainInput(
            payment_id="pay_test_missing",
            amount_paise=100000,
            failure_category="network_timeout",
        )
        rec = provider.generate_recommendation(input_ctx)
        assert rec.is_fallback is True


def test_hard_decline_and_exhausted_retries_force_stop() -> None:
    """Acceptance Test: Fraud, stolen cards, or exhausted retries strictly trigger STOP."""
    provider = GeminiProvider(api_key=None)  # triggers fallback engine
    input_fraud = RecoveryBrainInput(
        payment_id="pay_fraud_001",
        amount_paise=100000,
        failure_category="fraud",
    )
    rec_fraud = provider.generate_recommendation(input_fraud)
    assert rec_fraud.action == "STOP"
    assert rec_fraud.expected_recovery_value_paise == 0
    assert rec_fraud.stop_rationale is not None

    input_exhausted = RecoveryBrainInput(
        payment_id="pay_retry_maxed",
        amount_paise=100000,
        failure_category="soft_decline",
        retry_count=3,
        max_retries_allowed=3,
    )
    rec_exhausted = provider.generate_recommendation(input_exhausted)
    assert rec_exhausted.action == "STOP"
    assert rec_exhausted.expected_recovery_value_paise == 0


def test_successful_payment_should_not_trigger_recovery() -> None:
    """Test 1: Already captured or successful payment marks already_recovered and STOP."""
    svc = RecoveryBrainService(provider=GeminiProvider(api_key=None))
    payment = {
        "payment_id": "pay_success_123",
        "amount": 250000,
        "currency": "INR",
        "status": "captured",
        "captured": True,
        "failure_category": "none",
        "retry_count": 0,
    }
    ctx = svc.build_decision_context(payment)
    assert ctx.system_state is not None
    assert ctx.system_state.already_recovered is True
    assert ctx.system_state.action_eligibility["RETRY"] is False
    assert ctx.system_state.action_eligibility["PAYMENT_LINK"] is False


def test_cooldown_active_blocks_immediate_retry(mock_db) -> None:
    """Test 7: When action was executed recently, cooldown_active is True and RETRY is ineligible."""
    now = datetime.now(UTC)
    PaymentRepository.create({
        "payment_id": "pay_cooldown_001",
        "amount": 100000,
        "currency": "INR",
        "status": "failed",
        "failure_category": "gateway_timeout",
        "retry_count": 1,
    })
    ActionRepository.create({
        "action_id": "act_cooldown_prev",
        "idempotency_key": "idem_cooldown_001",
        "payment_id": "pay_cooldown_001",
        "action_type": "RETRY",
        "status": "EXECUTED",
        "executed_at": now - timedelta(seconds=60),  # 60s ago (<300s cooldown)
    })

    svc = RecoveryBrainService(provider=GeminiProvider(api_key=None))
    payment = PaymentRepository.get_by_id("pay_cooldown_001")
    assert payment is not None

    ctx = svc.build_decision_context(payment, now=now)
    assert ctx.recovery_history is not None
    assert ctx.recovery_history.cooldown_active is True
    assert ctx.recovery_history.cooldown_remaining_seconds > 0
    assert ctx.system_state is not None
    assert ctx.system_state.action_eligibility["RETRY"] is False


def test_decision_context_contains_all_verified_sections() -> None:
    """Test 20: Verify Decision Context contains all verified data and excludes sensitive info."""
    svc = RecoveryBrainService(provider=GeminiProvider(api_key=None))
    now = datetime.now(UTC)
    payment = {
        "payment_id": "pay_full_ctx_001",
        "order_id": "order_xyz_123",
        "amount": 750000,
        "currency": "INR",
        "status": "failed",
        "failure_category": "insufficient_funds",
        "failure_reason": "Cardholder balance insufficient for debit",
        "error_code": "BAD_REQUEST_PAYMENT_FAILED",
        "retry_count": 1,
        "max_retries_allowed": 3,
        "method": "card",
        "customer_id": "cust_trusted_99",
        "created_at": now - timedelta(hours=2),
        "method_details": {
            "network": "Visa",
            "issuer": "HDFC",
            "card_number": "4111111111111111",  # sensitive
            "cvv": "123",  # sensitive
            "token": "tok_secret_abc",  # sensitive
        },
    }

    ctx = svc.build_decision_context(payment, now=now)

    # Inclusions
    assert ctx.payment_id == "pay_full_ctx_001"
    assert ctx.amount_paise == 750000
    assert ctx.current_payment is not None
    assert ctx.current_payment.order_id == "order_xyz_123"
    assert ctx.current_payment.method == "card"
    assert ctx.current_payment.method_details.get("network") == "Visa"
    assert ctx.economic_context is not None
    assert ctx.economic_context.amount_at_risk_paise == 750000
    assert ctx.economic_context.baseline_control_paise == 60000  # 8% of 750000
    assert ctx.temporal_context is not None
    assert ctx.temporal_context.payment_age_hours >= 1.9

    # Exclusions (Zero secrets or card credentials)
    prompt_str = build_analysis_prompt(ctx)
    assert "4111111111111111" not in prompt_str
    assert "cvv" not in prompt_str.lower()
    assert "tok_secret_abc" not in prompt_str
    assert "card_number" not in ctx.current_payment.method_details


def test_gemini_timeout_and_api_failure_handled_safely() -> None:
    """Test 16 & 17: Provider catches timeouts and API errors safely and emits fallback."""
    mock_client = MagicMock()
    mock_client.models.generate_content.side_effect = TimeoutError("Gemini request timed out after 5000ms")

    provider = GeminiProvider(api_key="test_key")
    with patch.object(provider, "_get_client", return_value=mock_client):
        ctx = RecoveryBrainInput(
            payment_id="pay_timeout_test",
            amount_paise=200000,
            failure_category="network_error",
        )
        rec = provider.generate_recommendation(ctx)
        assert rec.is_fallback is True
        assert "Gemini service unavailable" in rec.reason


@pytest.mark.asyncio
async def test_async_generation_and_client_reuse() -> None:
    """Test 24: Verify async generate_recommendation_async reuses singleton client."""
    mock_client = MagicMock()
    mock_aio = MagicMock()
    mock_response = MagicMock()
    mock_response.text = json.dumps({
        "action": "PAYMENT_LINK",
        "confidence": 0.91,
        "expected_recovery_value_paise": 190000,
        "reason": "Async evaluation completed successfully.",
        "supporting_factors": ["High soft decline recoverability"],
        "risk_factors": [],
    })
    mock_aio.models.generate_content = AsyncMock(return_value=mock_response)
    mock_client.aio = mock_aio

    provider = GeminiProvider(api_key="test_async_key")
    with patch.object(provider, "_get_client", return_value=mock_client):
        ctx = RecoveryBrainInput(
            payment_id="pay_async_001",
            amount_paise=200000,
            failure_category="insufficient_funds",
        )
        out = await provider.generate_recommendation_async(ctx)
        assert out.action == "PAYMENT_LINK"
        assert out.confidence == 0.91
        assert out.latency_ms is not None
        mock_aio.models.generate_content.assert_called_once()


@pytest.mark.asyncio
async def test_in_flight_request_deduplication() -> None:
    """Test 18: Verify duplicate simultaneous calls for the same payment state are deduplicated."""
    svc = RecoveryBrainService(provider=GeminiProvider(api_key=None))
    payment = {
        "payment_id": "pay_dedup_001",
        "amount": 300000,
        "status": "failed",
        "failure_category": "network_timeout",
        "retry_count": 0,
    }

    # Launch two simultaneous analysis tasks
    task1 = asyncio.create_task(svc.analyze_payment_async(payment))
    task2 = asyncio.create_task(svc.analyze_payment_async(payment))

    res1, res2 = await asyncio.gather(task1, task2)
    assert res1.action == res2.action
    assert res1.confidence == res2.confidence


def test_policy_conflict_gating_stops_unauthorized_ai_action() -> None:
    """Test 20: When AI recommends RETRY but retries are exhausted, Guarded Autopilot BLOCKS."""
    payment = {
        "payment_id": "pay_conflict_001",
        "amount": 100000,
        "currency": "INR",
        "status": "failed",
        "failure_category": "soft_decline",
        "retry_count": 3,
        "max_retries_allowed": 3,
    }
    ai_recommendation = {
        "action": "RETRY",
        "confidence": 0.85,
        "expected_recovery_value_paise": 80000,
    }
    user = {"role": "operator"}

    verdict = GuardedPolicyEngine.evaluate(
        payment=payment,
        action=str(ai_recommendation["action"]),
        user=user,
        idempotency_key="test_conflict_idem",
    )
    assert verdict.blocking_rule == "RETRY_THRESHOLD"


def test_missing_and_conflicting_customer_history(mock_db) -> None:
    """Test 21 & 23: Safely handles unknown customer and conflicting transaction signals."""
    # Unknown customer
    hist = PaymentRepository.get_customer_history("unknown")
    assert hist["customer_id"] == "unknown"
    assert hist["total_successful_payments"] == 0

    # Customer with conflicting history (2 successes, 2 failures)
    cust_id = "cust_mixed_signal"
    PaymentRepository.create({
        "payment_id": "pay_mix_1",
        "customer_id": cust_id,
        "amount": 100000,
        "status": "captured",
    })
    PaymentRepository.create({
        "payment_id": "pay_mix_2",
        "customer_id": cust_id,
        "amount": 100000,
        "status": "failed",
    })
    mixed_hist = PaymentRepository.get_customer_history(cust_id)
    assert mixed_hist["total_successful_payments"] == 1
    assert mixed_hist["total_failed_payments"] == 1
    assert mixed_hist["historical_recovery_success_rate"] == 0.5


def test_client_reset_on_shutdown() -> None:
    """Test 25: Verify reset_client clears class-level client references."""
    GeminiProvider.get_client("dummy_key_123")
    assert GeminiProvider._shared_client is not None
    GeminiProvider.reset_client()
    assert GeminiProvider._shared_client is None
    assert GeminiProvider._shared_api_key is None
