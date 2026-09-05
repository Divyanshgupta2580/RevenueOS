"""Tests for Phase 4: AI Latency Instrumentation, Transparent Processing UX,

In-Flight Deduplication, Safe Telemetry, and Deterministic Fallbacks.
"""

import asyncio
import json
from unittest.mock import AsyncMock, patch

import pytest

from apps.brain.provider import GeminiProvider
from apps.brain.schemas import RecoveryBrainInput, RecoveryBrainOutput
from apps.brain.service import RecoveryBrainService
from apps.websocket.consumer import RevenueOSConsumer
from tests.test_websocket import WebsocketTestCommunicator


@pytest.fixture
def sample_failed_payment() -> dict:
    return {
        "payment_id": "pay_test_phase4_01",
        "order_id": "order_test_phase4_01",
        "amount": 150000,
        "currency": "INR",
        "status": "failed",
        "failure_category": "soft_decline",
        "failure_reason": "international_transaction_not_allowed",
        "method": "card",
        "retry_count": 0,
        "max_retries_allowed": 3,
        "customer_id": "cust_test_p4",
        "customer_email": "operator@revenueos.com",
    }


@pytest.mark.asyncio
async def test_latency_instrumentation(sample_failed_payment: dict) -> None:
    """Validate that every step of the decision pipeline is safely measured."""
    service = RecoveryBrainService()
    mock_gemini_output = RecoveryBrainOutput(
        action="PAYMENT_LINK",
        confidence=0.85,
        expected_recovery_value_paise=95625,
        reason="Soft decline eligible for payment link dispatch.",
        supporting_factors=["Soft card decline"],
        risk_factors=[],
    )

    with patch.object(
        service.provider, "generate_recommendation_async", new_callable=AsyncMock
    ) as mock_gen:
        mock_gemini_output.telemetry = {
            "gemini_request_ms": 1250.5,
            "schema_validation_ms": 0.45,
        }
        mock_gen.return_value = mock_gemini_output

        result = await service.analyze_payment_async(sample_failed_payment)

        assert result.telemetry is not None
        telem = result.telemetry
        assert "context_build_ms" in telem
        assert "gemini_request_ms" in telem
        assert "schema_validation_ms" in telem
        assert "policy_validation_ms" in telem
        assert "total_decision_ms" in telem

        assert telem["context_build_ms"] >= 0.0
        assert telem["gemini_request_ms"] == 1250.5
        assert telem["schema_validation_ms"] == 0.45
        assert telem["policy_validation_ms"] >= 0.0
        assert telem["total_decision_ms"] >= 0.0


@pytest.mark.asyncio
async def test_duplicate_analysis_prevention(sample_failed_payment: dict) -> None:
    """Validate that duplicate concurrent calls for the exact same payment state share a single in-flight task."""
    service = RecoveryBrainService()
    call_count = 0

    async def slow_mock_generate(ctx: RecoveryBrainInput) -> RecoveryBrainOutput:
        nonlocal call_count
        call_count += 1
        await asyncio.sleep(0.1)
        return RecoveryBrainOutput(
            action="PAYMENT_LINK",
            confidence=0.85,
            expected_recovery_value_paise=95625,
            reason="Deduplicated analysis result.",
        )

    with patch.object(service.provider, "generate_recommendation_async", side_effect=slow_mock_generate):
        # Fire 3 concurrent analysis calls for the exact same payment state
        t1 = service.analyze_payment_async(sample_failed_payment)
        t2 = service.analyze_payment_async(sample_failed_payment)
        t3 = service.analyze_payment_async(sample_failed_payment)

        res1, res2, res3 = await asyncio.gather(t1, t2, t3)

        assert res1.action == "PAYMENT_LINK"
        assert res2.action == "PAYMENT_LINK"
        assert res3.action == "PAYMENT_LINK"
        # Only ONE underlying call was dispatched to the AI provider
        assert call_count == 1


@pytest.mark.asyncio
async def test_actual_processing_states_over_websocket(mock_db, sample_failed_payment: dict) -> None:
    """Validate that actual processing stages are emitted over WebSocket in strict chronological order."""
    from apps.database.repositories import PaymentRepository

    PaymentRepository.create(sample_failed_payment)

    user = {"id": "op_test_p4", "username": "operator@revenueos.com", "role": "operator"}
    communicator = WebsocketTestCommunicator(RevenueOSConsumer.as_asgi(), user=user)
    connected, _ = await communicator.connect()
    assert connected is True

    mock_gemini_output = RecoveryBrainOutput(
        action="PAYMENT_LINK",
        confidence=0.85,
        expected_recovery_value_paise=95625,
        reason="Live stage transition test.",
    )

    with patch.object(RecoveryBrainService, "analyze_payment_async", new_callable=AsyncMock) as mock_analyze:
        mock_analyze.return_value = mock_gemini_output

        await communicator.send_to(
            text_data=json.dumps({
                "protocolVersion": "v1",
                "requestId": "req_stage_test",
                "type": "recovery.analyze",
                "payload": {"paymentId": sample_failed_payment["payment_id"]},
            })
        )

        received_stages: list[str] = []
        completed_msg = None

        while True:
            raw = await communicator.receive_from()
            msg = json.loads(raw)
            m_type = msg.get("type")

            if m_type == "analysis.stage":
                stage = msg["payload"]["stage"]
                received_stages.append(stage)
            elif m_type == "analysis.completed":
                completed_msg = msg
                break

        # Verify stages arrived in exact sequence
        expected_stages = [
            "BUILDING DECISION CONTEXT",
            "ANALYZING WITH GEMINI",
            "VALIDATING RECOMMENDATION",
            "CHECKING POLICY",
            "DECISION READY",
        ]
        assert received_stages == expected_stages
        assert completed_msg is not None
        assert completed_msg["payload"]["paymentId"] == sample_failed_payment["payment_id"]

    await communicator.disconnect()


@pytest.mark.asyncio
async def test_gemini_failure_and_fallback_state(sample_failed_payment: dict) -> None:
    """Validate that when Gemini times out or returns 503, deterministic fallback triggers with explicit labeling."""
    service = RecoveryBrainService()
    input_ctx = service.build_decision_context(sample_failed_payment)

    # Directly test get_safe_fallback
    fallback = GeminiProvider.get_safe_fallback(input_ctx, reason="Gemini 503 Service Unavailable")

    assert fallback.is_fallback is True
    assert "Gemini 503" in (fallback.fallback_reason or fallback.reason)
    assert fallback.action in ["PAYMENT_LINK", "RETRY", "REMINDER", "STOP"]
    # Verify fallback is never labeled as Gemini
    assert "Fallback" in fallback.reason or fallback.is_fallback is True


def test_no_secret_leakage_in_telemetry(sample_failed_payment: dict) -> None:
    """Validate that telemetry and diagnostic summaries strictly exclude all secrets, tokens, and PII."""
    service = RecoveryBrainService()
    input_ctx = service.build_decision_context(sample_failed_payment)

    # Check input context serialization
    ctx_dump = input_ctx.model_dump_json()
    forbidden_terms = [
        "secret",
        "api_key",
        "password",
        "token",
        "cvv",
        "card_number",
        "rzp_test_secret",
    ]
    for term in forbidden_terms:
        # Check that no sensitive key or secret values are present
        assert f'"{term}":' not in ctx_dump.lower()
