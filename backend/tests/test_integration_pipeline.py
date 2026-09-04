"""Acceptance tests for Phase 11: Full Integration Pipeline.

Verifies end-to-end flow:
Payment Ingestion -> Revenue Radar -> Gemini Recovery Brain -> Guarded Autopilot
-> Razorpay Test Execution -> Signed Webhook Capture -> Outcome Metrics -> Live WebSocket Broadcast

NOTE: All transactions and payment records in this test module are SYNTHETIC EVALUATION
TEST FIXTURES used solely to verify algorithmic pipeline correctness and idempotency in an isolated
in-memory test database. They never enter or pollute production database pathways.
"""

import hashlib
import hmac
import json
from unittest.mock import patch

import pytest
from django.test import Client

from apps.brain.schemas import RecoveryBrainOutput
from apps.database.repositories import (
    ActionRepository,
    DecisionRepository,
    PaymentRepository,
)
from apps.websocket.consumer import RevenueOSConsumer
from tests.test_websocket import WebsocketTestCommunicator


@pytest.fixture
def webhook_secret(settings) -> str:
    secret = "rzp_test_secret_pipeline_xyz"
    settings.RAZORPAY_WEBHOOK_SECRET = secret
    return secret


def _sign(body: bytes, secret: str) -> str:
    return hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


@pytest.mark.asyncio
async def test_full_end_to_end_recovery_pipeline(client: Client, mock_db, webhook_secret: str) -> None:
    """Acceptance Test: Complete recovery pipeline from payment to webhook capture and metric update."""
    # Step 1: Seed a failed transaction at risk (₹5,000.00 / 500,000 paise)
    PaymentRepository.create({
        "payment_id": "pay_pipe_001",
        "amount": 500000,
        "currency": "INR",
        "status": "failed",
        "failure_category": "insufficient_funds",
        "failure_reason": "Payment failed due to low balance",
        "retry_count": 0,
        "max_retries_allowed": 3,
        "customer_email": "operator@test.com",
    })

    # Step 2: Connect WebSocket as authenticated operator
    user = {"id": "usr_operator_1", "username": "lead_operator", "role": "operator"}
    communicator = WebsocketTestCommunicator(RevenueOSConsumer.as_asgi(), user=user)
    await communicator.connect()

    # Step 3: Request opportunities list over WebSocket
    await communicator.send_to(text_data=json.dumps({
        "protocolVersion": "v1",
        "requestId": "req_pipe_list",
        "type": "revenue.list",
        "payload": {},
    }))
    list_res = json.loads(await communicator.receive_from())
    assert list_res["type"] == "revenue.list.response"
    opps = list_res["payload"]["opportunities"]
    assert len(opps) == 1
    target_opp = opps[0]
    assert target_opp["paymentId"] == "pay_pipe_001"
    assert target_opp["amountPaise"] == 500000
    assert target_opp["recoverabilityScore"] > 0
    assert target_opp["expectedRecoveryValuePaise"] > 0

    # Step 4: Request Gemini Recovery Brain analysis
    mock_brain_output = RecoveryBrainOutput(
        action="PAYMENT_LINK",
        confidence=0.88,
        expected_recovery_value_paise=420000,
        reason="High-value opportunity with low retry count; customer payment link optimal.",
        supportingFactors=["Zero prior retries", "Recoverability score > 70"],
        riskFactors=["Insufficient funds transient error"],
        reasoningSummary="Issuing payment link is safest and yields highest expected recovery value.",
    )

    from apps.brain.service import RecoveryBrainService

    with patch.object(RecoveryBrainService, "analyze_payment", return_value=mock_brain_output):
        await communicator.send_to(text_data=json.dumps({
            "protocolVersion": "v1",
            "requestId": "req_pipe_analyze",
            "type": "recovery.analyze",
            "payload": {"paymentId": "pay_pipe_001"},
        }))
        # analysis.started
        start_msg = json.loads(await communicator.receive_from())
        assert start_msg["type"] == "analysis.started"

        # analysis.completed
        complete_msg = json.loads(await communicator.receive_from())
        assert complete_msg["type"] == "analysis.completed"
        rec = complete_msg["payload"]["recommendation"]
        assert rec["action"] == "PAYMENT_LINK"
        assert rec["confidence"] == 0.88

    # Step 5: Execute action via Guarded Autopilot
    await communicator.send_to(text_data=json.dumps({
        "protocolVersion": "v1",
        "requestId": "req_pipe_exec",
        "type": "recovery.execute",
        "payload": {
            "paymentId": "pay_pipe_001",
            "action": "PAYMENT_LINK",
            "idempotencyKey": "idemp_pipe_exec_001",
            "aiRecommendation": rec,
        },
    }))

    # recovery.approved
    app_msg = json.loads(await communicator.receive_from())
    assert app_msg["type"] == "recovery.approved"
    assert app_msg["payload"]["action"] == "PAYMENT_LINK"
    decision_id = app_msg["payload"]["decisionId"]

    # recovery.executed
    exec_msg = json.loads(await communicator.receive_from())
    assert exec_msg["type"] == "recovery.executed"
    assert exec_msg["payload"]["status"] in ["EXECUTED", "QUEUED"]
    action_id = exec_msg["payload"]["actionId"]

    # Verify database state after execution
    action_record = ActionRepository.get_by_idempotency_key("idemp_pipe_exec_001")
    assert action_record is not None
    assert action_record["status"] == "EXECUTED"
    assert action_record["outcome"] == "PENDING"

    decision_record = DecisionRepository.get_by_id(decision_id)
    assert decision_record is not None
    assert decision_record["policy_decision"]["status"] == "APPROVED"

    updated_payment = PaymentRepository.get_by_id("pay_pipe_001")
    assert updated_payment is not None
    assert updated_payment["recovery_status"] == "link_sent"

    # Step 6: Customer pays via link -> Razorpay triggers webhook: payment.captured
    webhook_payload = {
        "id": "evt_pipe_capture_001",
        "event": "payment.captured",
        "payload": {
            "payment": {
                "entity": {
                    "id": "pay_pipe_001",
                    "amount": 500000,
                    "status": "captured",
                }
            }
        },
    }
    body = json.dumps(webhook_payload).encode("utf-8")
    sig = _sign(body, webhook_secret)

    hook_resp = client.post(
        "/api/webhooks/razorpay/",
        data=body,
        content_type="application/json",
        HTTP_X_RAZORPAY_SIGNATURE=sig,
    )
    assert hook_resp.status_code == 200

    # Step 7: Verify live broadcast was received by connected operator WebSocket
    ws_notification = json.loads(await communicator.receive_from())
    assert ws_notification["type"] in ["payment.updated", "revenue.updated"]
    ws_notification_2 = json.loads(await communicator.receive_from())
    assert ws_notification_2["type"] in ["payment.updated", "revenue.updated"]

    # Step 8: Verify payment is now recovered and action is marked RECOVERED
    recovered_payment = PaymentRepository.get_by_id("pay_pipe_001")
    assert recovered_payment is not None
    assert recovered_payment["status"] == "captured"
    assert recovered_payment["recovery_status"] == "recovered"

    recovered_action = ActionRepository.get_by_id(action_id)
    assert recovered_action is not None
    assert recovered_action["outcome"] == "RECOVERED"

    # Step 9: Request live Metrics summary over WebSocket
    await communicator.send_to(text_data=json.dumps({
        "protocolVersion": "v1",
        "requestId": "req_pipe_metrics",
        "type": "metrics.summary",
        "payload": {},
    }))
    metric_msg = json.loads(await communicator.receive_from())
    assert metric_msg["type"] == "metrics.summary.response"
    m = metric_msg["payload"]

    assert m["actuallyRecoveredPaise"] == 500000
    assert m["revenueAtRiskPaise"] == 0
    assert m["recoveryRate"] == 1.0

    await communicator.disconnect()


@pytest.mark.asyncio
async def test_policy_blocked_action_never_reaches_execution(mock_db) -> None:
    """Acceptance Test: Hard-decline fraud payment is blocked by policy and never executed."""
    # Seed high-risk fraud payment
    PaymentRepository.create({
        "payment_id": "pay_fraud_pipeline",
        "amount": 1000000,
        "status": "failed",
        "failure_category": "fraud",
        "retry_count": 0,
    })

    user = {"id": "usr_op", "username": "operator", "role": "operator"}
    communicator = WebsocketTestCommunicator(RevenueOSConsumer.as_asgi(), user=user)
    await communicator.connect()

    # Operator attempts to RETRY a fraud payment
    await communicator.send_to(text_data=json.dumps({
        "protocolVersion": "v1",
        "requestId": "req_fraud_exec",
        "type": "recovery.execute",
        "payload": {
            "paymentId": "pay_fraud_pipeline",
            "action": "RETRY",
            "idempotencyKey": "idemp_fraud_pipe_001",
        },
    }))

    res = json.loads(await communicator.receive_from())
    assert res["type"] == "recovery.blocked"
    assert res["payload"]["blockingRule"] == "RISK_POLICY"
    decision_id = res["payload"]["decisionId"]

    # Verify decision is persisted as BLOCKED
    decision_doc = DecisionRepository.get_by_id(decision_id)
    assert decision_doc is not None
    assert decision_doc["policy_decision"]["status"] == "BLOCKED"

    # Verify no action was executed in recovery_actions
    action_doc = ActionRepository.get_by_idempotency_key("idemp_fraud_pipe_001")
    assert action_doc is None

    # Verify payment remains uncorrupted
    p = PaymentRepository.get_by_id("pay_fraud_pipeline")
    assert p is not None
    assert p["status"] == "failed"
    assert p["retry_count"] == 0

    await communicator.disconnect()


@pytest.mark.asyncio
async def test_idempotency_prevents_duplicate_action_and_duplicate_webhook(
    client: Client, mock_db, webhook_secret: str
) -> None:
    """Acceptance Test: Duplicate action requests and replay webhooks are safely deduplicated."""
    PaymentRepository.create({
        "payment_id": "pay_idemp_pipeline",
        "amount": 250000,
        "status": "failed",
        "retry_count": 0,
        "max_retries_allowed": 3,
    })

    user = {"id": "usr_op", "username": "operator", "role": "operator"}
    communicator = WebsocketTestCommunicator(RevenueOSConsumer.as_asgi(), user=user)
    await communicator.connect()

    # First execution attempt
    await communicator.send_to(text_data=json.dumps({
        "protocolVersion": "v1",
        "requestId": "req_idemp_1",
        "type": "recovery.execute",
        "payload": {
            "paymentId": "pay_idemp_pipeline",
            "action": "PAYMENT_LINK",
            "idempotencyKey": "idemp_same_key_999",
        },
    }))
    msg1 = json.loads(await communicator.receive_from())
    assert msg1["type"] == "recovery.approved"
    msg2 = json.loads(await communicator.receive_from())
    assert msg2["type"] == "recovery.executed"

    # Second execution attempt with identical idempotencyKey
    await communicator.send_to(text_data=json.dumps({
        "protocolVersion": "v1",
        "requestId": "req_idemp_2",
        "type": "recovery.execute",
        "payload": {
            "paymentId": "pay_idemp_pipeline",
            "action": "PAYMENT_LINK",
            "idempotencyKey": "idemp_same_key_999",
        },
    }))
    msg3 = json.loads(await communicator.receive_from())
    assert msg3["type"] == "error"
    assert msg3["error"]["code"] == "DUPLICATE_EXECUTION"

    # Inbound Webhook deduplication test
    webhook_payload = {
        "id": "evt_replay_001",
        "event": "payment.captured",
        "payload": {
            "payment": {
                "entity": {
                    "id": "pay_idemp_pipeline",
                    "amount": 250000,
                    "status": "captured",
                }
            }
        },
    }
    body = json.dumps(webhook_payload).encode("utf-8")
    sig = _sign(body, webhook_secret)

    # First delivery
    resp1 = client.post(
        "/api/webhooks/razorpay/",
        data=body,
        content_type="application/json",
        HTTP_X_RAZORPAY_SIGNATURE=sig,
    )
    assert resp1.status_code == 200
    assert resp1.json()["outcome"]["status"] == "PROCESSED"

    # Read notification on WS
    ws_notif = json.loads(await communicator.receive_from())
    assert ws_notif["type"] in ["payment.updated", "revenue.updated"]

    # Replay identical webhook
    resp2 = client.post(
        "/api/webhooks/razorpay/",
        data=body,
        content_type="application/json",
        HTTP_X_RAZORPAY_SIGNATURE=sig,
    )
    assert resp2.status_code == 200
    assert resp2.json()["outcome"]["status"] == "ALREADY_PROCESSED"

    await communicator.disconnect()

