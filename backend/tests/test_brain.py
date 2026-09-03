"""Acceptance tests for Phase 6: Recovery Brain & Gemini SDK."""

import json
from unittest.mock import MagicMock, patch

import pytest

from apps.brain.provider import GeminiProvider
from apps.brain.schemas import RecoveryBrainInput, RecoveryBrainOutput
from apps.brain.service import RecoveryBrainService
from apps.database.repositories import DecisionRepository, PaymentRepository
from apps.websocket.consumer import RevenueOSConsumer
from tests.test_websocket import WebsocketTestCommunicator


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


def test_ai_cannot_mutate_database_directly(mock_db) -> None:
    """Acceptance Test: Recovery Brain service performs no database writes."""
    payment = {
        "payment_id": "pay_audit_test",
        "amount": 200000,
        "failure_category": "network_timeout",
        "status": "failed",
    }
    PaymentRepository.create(payment)

    svc = RecoveryBrainService()
    svc.analyze_payment(payment)

    # Verify payment document in DB remains completely unchanged
    db_payment = PaymentRepository.get_by_id("pay_audit_test")
    assert db_payment is not None
    assert db_payment["status"] == "failed"
    assert db_payment["recovery_status"] == "pending"
    assert db_payment["last_recovery_action_id"] is None


def test_decision_persistence_for_audit(mock_db) -> None:
    """Acceptance Test: Machine-validated recommendation is persisted to recovery_decisions."""
    decision_doc = {
        "decision_id": "dec_audit_001",
        "payment_id": "pay_audit_test",
        "model_version": "gemini-2.0-flash",
        "ai_recommendation": {
            "action": "PAYMENT_LINK",
            "confidence": 0.85,
            "expected_recovery_value_paise": 150000,
            "reason": "Audit verification decision",
        },
        "policy_decision": {"status": "APPROVED"},
    }
    created = DecisionRepository.create(decision_doc)
    assert created["decision_id"] == "dec_audit_001"

    retrieved = DecisionRepository.get_by_id("dec_audit_001")
    assert retrieved is not None
    assert retrieved["ai_recommendation"]["action"] == "PAYMENT_LINK"


@pytest.mark.asyncio
async def test_websocket_recovery_analyze_flow(mock_db) -> None:
    """Acceptance Test: WebSocket recovery.analyze emits started then completed."""
    PaymentRepository.create({
        "payment_id": "pay_ws_brain_001",
        "amount": 300000,
        "status": "failed",
        "failure_category": "network_timeout",
    })

    user = {"id": "usr_test", "username": "operator"}
    communicator = WebsocketTestCommunicator(RevenueOSConsumer.as_asgi(), user=user)
    await communicator.connect()

    analyze_frame = {
        "protocolVersion": "v1",
        "requestId": "req_brain_001",
        "type": "recovery.analyze",
        "payload": {"paymentId": "pay_ws_brain_001"},
    }
    await communicator.send_to(text_data=json.dumps(analyze_frame))

    # 1. First event: analysis.started
    msg1 = json.loads(await communicator.receive_from())
    assert msg1["type"] == "analysis.started"
    assert msg1["payload"]["paymentId"] == "pay_ws_brain_001"

    # 2. Second event: analysis.completed
    msg2 = json.loads(await communicator.receive_from())
    assert msg2["type"] == "analysis.completed"
    assert msg2["payload"]["paymentId"] == "pay_ws_brain_001"
    assert "recommendation" in msg2["payload"]
    assert msg2["payload"]["recommendation"]["action"] in ["RETRY", "PAYMENT_LINK", "REMINDER", "STOP"]

    await communicator.disconnect()
