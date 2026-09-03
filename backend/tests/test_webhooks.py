"""Acceptance tests for Phase 9: Signed Razorpay Webhook Pipeline."""

import hashlib
import hmac
import json

import pytest
from django.test import Client

from apps.database.repositories import ActionRepository, PaymentRepository, WebhookEventRepository
from apps.websocket.consumer import RevenueOSConsumer
from tests.test_websocket import WebsocketTestCommunicator


@pytest.fixture
def webhook_secret(settings) -> str:
    secret = "rzp_webhook_secret_test_xyz"
    settings.RAZORPAY_WEBHOOK_SECRET = secret
    return secret


def _sign(body: bytes, secret: str) -> str:
    return hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


def test_valid_webhook_payment_captured(client: Client, mock_db, webhook_secret: str) -> None:
    """Acceptance Test: Valid HMAC-signed payment.captured updates payment to captured & recovered."""
    # Seed payment in failed state
    PaymentRepository.create({
        "payment_id": "pay_hook_001",
        "amount": 350000,
        "status": "failed",
        "recovery_status": "link_sent",
    })
    ActionRepository.create({
        "action_id": "act_hook_001",
        "payment_id": "pay_hook_001",
        "idempotency_key": "idemp_act_hook_001",
        "action_type": "PAYMENT_LINK",
        "status": "EXECUTED",
        "outcome": "PENDING",
    })

    payload = {
        "id": "evt_hook_001",
        "event": "payment.captured",
        "payload": {
            "payment": {
                "entity": {
                    "id": "pay_hook_001",
                    "amount": 350000,
                    "status": "captured",
                }
            }
        },
    }
    body = json.dumps(payload).encode("utf-8")
    sig = _sign(body, webhook_secret)

    response = client.post(
        "/api/webhooks/razorpay/",
        data=body,
        content_type="application/json",
        HTTP_X_RAZORPAY_SIGNATURE=sig,
    )

    assert response.status_code == 200
    res_data = response.json()
    assert res_data["status"] == "ok"
    assert res_data["outcome"]["status"] == "PROCESSED"

    # Payment record updated
    p = PaymentRepository.get_by_id("pay_hook_001")
    assert p is not None
    assert p["status"] == "captured"
    assert p["recovery_status"] == "recovered"

    # Action record updated
    act = ActionRepository.get_by_idempotency_key("idemp_act_hook_001")
    assert act is not None
    assert act["outcome"] == "RECOVERED"

    # Event persisted in audit collection
    assert WebhookEventRepository.is_processed("evt_hook_001") is True


def test_invalid_signature_rejected(client: Client, mock_db, webhook_secret: str) -> None:
    """Acceptance Test: Webhook with forged or mismatched HMAC signature is rejected."""
    body = json.dumps({"id": "evt_fraud_001", "event": "payment.captured"}).encode("utf-8")
    bad_sig = "a" * 64

    response = client.post(
        "/api/webhooks/razorpay/",
        data=body,
        content_type="application/json",
        HTTP_X_RAZORPAY_SIGNATURE=bad_sig,
    )

    assert response.status_code == 400
    assert response.json()["error"] == "INVALID_SIGNATURE"


def test_missing_signature_rejected(client: Client, mock_db, webhook_secret: str) -> None:
    """Acceptance Test: Webhook without signature header is rejected."""
    body = json.dumps({"id": "evt_nosig_001", "event": "payment.captured"}).encode("utf-8")

    response = client.post(
        "/api/webhooks/razorpay/",
        data=body,
        content_type="application/json",
    )

    assert response.status_code == 400
    assert response.json()["error"] == "INVALID_SIGNATURE"


def test_malformed_json_payload_rejected(client: Client, mock_db, webhook_secret: str) -> None:
    """Acceptance Test: Webhook with non-JSON body is rejected."""
    body = b"NOT_A_JSON_PAYLOAD_{{"
    sig = _sign(body, webhook_secret)

    response = client.post(
        "/api/webhooks/razorpay/",
        data=body,
        content_type="application/json",
        HTTP_X_RAZORPAY_SIGNATURE=sig,
    )

    assert response.status_code == 400
    assert response.json()["error"] == "MALFORMED_PAYLOAD"


def test_duplicate_webhook_processed_only_once(client: Client, mock_db, webhook_secret: str) -> None:
    """Acceptance Test: Replaying identical event_id is safely ignored (idempotent)."""
    payload = {
        "id": "evt_dup_001",
        "event": "payment.captured",
        "payload": {"payment": {"entity": {"id": "pay_dup_001"}}},
    }
    body = json.dumps(payload).encode("utf-8")
    sig = _sign(body, webhook_secret)

    # First attempt
    res1 = client.post("/api/webhooks/razorpay/", data=body, content_type="application/json", HTTP_X_RAZORPAY_SIGNATURE=sig)
    assert res1.status_code == 200
    assert res1.json()["outcome"]["status"] == "PROCESSED"

    # Second replay attempt
    res2 = client.post("/api/webhooks/razorpay/", data=body, content_type="application/json", HTTP_X_RAZORPAY_SIGNATURE=sig)
    assert res2.status_code == 200
    assert res2.json()["outcome"]["status"] == "ALREADY_PROCESSED"


@pytest.mark.asyncio
async def test_webhook_broadcasts_to_connected_operators(mock_db) -> None:
    """Acceptance Test: Inbound webhook event broadcasts live update to WebSocket operators group."""
    from apps.webhooks.processor import WebhookEventProcessor

    user = {"id": "usr_op", "username": "operator", "role": "operator"}
    communicator = WebsocketTestCommunicator(RevenueOSConsumer.as_asgi(), user=user)
    await communicator.connect()

    # Trigger processor broadcast
    WebhookEventProcessor.broadcast_to_operators("payment.updated", {"paymentId": "pay_live_001", "status": "captured"})

    msg = json.loads(await communicator.receive_from())
    assert msg["type"] == "payment.updated"
    assert msg["payload"]["paymentId"] == "pay_live_001"
    assert msg["payload"]["status"] == "captured"

    await communicator.disconnect()
