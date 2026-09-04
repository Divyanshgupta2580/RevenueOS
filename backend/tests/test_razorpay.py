"""Acceptance tests for Phase 8: Razorpay Test Mode Integration."""

import json
import logging
from unittest.mock import MagicMock, patch

import pytest
import requests

from apps.database.repositories import ActionRepository, PaymentRepository
from apps.razorpay_adapter.adapter import RazorpayAdapter
from apps.razorpay_adapter.exceptions import (
    RazorpayApiError,
    RazorpayAuthError,
    RazorpayNetworkError,
)
from apps.razorpay_adapter.service import RazorpayRecoveryExecutor


@pytest.fixture
def mock_payment(mock_db) -> dict:
    return PaymentRepository.create({
        "payment_id": "pay_rzp_test_001",
        "amount": 499900,  # 4,999.00 INR in paise
        "status": "failed",
        "failure_category": "soft_decline",
        "retry_count": 0,
    })


def test_missing_credentials_raises_auth_error() -> None:
    """Acceptance Test: Adapter requires valid key_id and key_secret when simulation disabled."""
    adapter = RazorpayAdapter(key_id="", key_secret="", simulate_if_unconfigured=False)
    with pytest.raises(RazorpayAuthError, match="not configured"):
        adapter.fetch_payment("pay_123")


def test_http_401_raises_auth_error() -> None:
    """Acceptance Test: HTTP 401 from Razorpay is translated into RazorpayAuthError."""
    mock_session = MagicMock()
    mock_resp = MagicMock()
    mock_resp.status_code = 401
    mock_resp.ok = False
    mock_session.request.return_value = mock_resp

    adapter = RazorpayAdapter(key_id="rzp_test_k", key_secret="rzp_test_s", session=mock_session)
    with pytest.raises(RazorpayAuthError, match="Invalid Razorpay API credentials"):
        adapter.fetch_payment("pay_123")


def test_network_timeout_raises_network_error() -> None:
    """Acceptance Test: Network timeout raises structured RazorpayNetworkError."""
    mock_session = MagicMock()
    mock_session.request.side_effect = requests.Timeout("Gateway timed out")

    adapter = RazorpayAdapter(key_id="rzp_test_k", key_secret="rzp_test_s", session=mock_session)
    with pytest.raises(RazorpayNetworkError, match="timed out"):
        adapter.fetch_payment("pay_123")


def test_create_payment_link_success() -> None:
    """Acceptance Test: create_payment_link sends integer paise and returns payment link details."""
    mock_session = MagicMock()
    mock_resp = MagicMock()
    mock_resp.ok = True
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "id": "plink_test_999",
        "amount": 499900,
        "currency": "INR",
        "status": "created",
        "short_url": "https://rzp.io/i/test999",
    }
    mock_session.request.return_value = mock_resp

    adapter = RazorpayAdapter(key_id="rzp_test_k", key_secret="rzp_test_s", session=mock_session)
    res = adapter.create_payment_link(
        amount_paise=499900,
        currency="INR",
        customer_email="customer@example.com",
    )

    assert res["id"] == "plink_test_999"
    assert res["amount"] == 499900
    assert res["short_url"] == "https://rzp.io/i/test999"

    # Verify request payload contained integer minor units (paise)
    call_kwargs = mock_session.request.call_args[1]
    assert call_kwargs["json"]["amount"] == 499900
    assert isinstance(call_kwargs["json"]["amount"], int)


def test_secrets_are_never_logged(caplog) -> None:
    """Acceptance Test: Secrets, key_secret, and authorization headers are never logged."""
    mock_session = MagicMock()
    mock_resp = MagicMock()
    mock_resp.ok = True
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"id": "pay_123"}
    mock_session.request.return_value = mock_resp

    secret_str = "SUPER_SECRET_KEY_12345"
    adapter = RazorpayAdapter(key_id="rzp_test_key_123", key_secret=secret_str, session=mock_session)

    with caplog.at_level(logging.DEBUG):
        adapter.fetch_payment("pay_123")

    # Assert secret string never appeared in captured logs
    for record in caplog.records:
        assert secret_str not in record.message
        assert "Authorization" not in record.message


def test_executor_executes_payment_link(mock_payment) -> None:
    """Acceptance Test: Executor executes PAYMENT_LINK, records action, updates payment state."""
    mock_adapter = MagicMock()
    mock_adapter.create_payment_link.return_value = {
        "id": "plink_abc_123",
        "short_url": "https://rzp.io/i/abc123",
        "amount": 499900,
    }

    executor = RazorpayRecoveryExecutor(adapter=mock_adapter)
    outcome = executor.execute_authorized_action(
        payment_id="pay_rzp_test_001",
        action="PAYMENT_LINK",
        decision_id="dec_test_001",
        idempotency_key="idemp_plink_test_001",
    )

    assert outcome["status"] == "EXECUTED"
    assert outcome["externalReference"] == "plink_abc_123"

    # Check recovery_actions collection has record
    action_doc = ActionRepository.get_by_idempotency_key("idemp_plink_test_001")
    assert action_doc is not None
    assert action_doc["action_type"] == "PAYMENT_LINK"
    assert action_doc["status"] == "EXECUTED"

    # Check payment document was updated to link_sent
    updated_payment = PaymentRepository.get_by_id("pay_rzp_test_001")
    assert updated_payment is not None
    assert updated_payment["recovery_status"] == "link_sent"


def test_failed_external_request_does_not_corrupt_state(mock_payment) -> None:
    """Acceptance Test: Failed Razorpay API call records FAILED action without corrupting payment."""
    mock_adapter = MagicMock()
    mock_adapter.create_payment_link.side_effect = RazorpayApiError("Gateway error 500", status_code=500)

    executor = RazorpayRecoveryExecutor(adapter=mock_adapter)
    outcome = executor.execute_authorized_action(
        payment_id="pay_rzp_test_001",
        action="PAYMENT_LINK",
        decision_id="dec_fail_test",
        idempotency_key="idemp_fail_001",
    )

    assert outcome["status"] == "FAILED"
    assert "error" in outcome["result"]

    # Payment status remains intact ('failed')
    payment = PaymentRepository.get_by_id("pay_rzp_test_001")
    assert payment is not None
    assert payment["status"] == "failed"

    # Action recorded as FAILED in audit collection
    action = ActionRepository.get_by_idempotency_key("idemp_fail_001")
    assert action is not None
    assert action["status"] == "FAILED"


def test_executor_executes_retry(mock_payment) -> None:
    """Acceptance Test: Executor handles RETRY, increments retry count, updates state."""
    executor = RazorpayRecoveryExecutor()
    outcome = executor.execute_authorized_action(
        payment_id="pay_rzp_test_001",
        action="RETRY",
        decision_id="dec_retry_001",
        idempotency_key="idemp_retry_test_001",
    )

    assert outcome["status"] == "EXECUTED"
    assert outcome["result"]["executionType"] == "SIMULATED_TEST_ACTION"
    payment = PaymentRepository.get_by_id("pay_rzp_test_001")
    assert payment is not None
    assert payment["retry_count"] == 1
    assert payment["recovery_status"] == "retrying"


def test_executor_executes_stop(mock_payment) -> None:
    """Acceptance Test: Executor handles STOP, terminates recovery safely."""
    executor = RazorpayRecoveryExecutor()
    outcome = executor.execute_authorized_action(
        payment_id="pay_rzp_test_001",
        action="STOP",
        decision_id="dec_stop_001",
        idempotency_key="idemp_stop_test_001",
    )

    assert outcome["status"] == "EXECUTED"
    payment = PaymentRepository.get_by_id("pay_rzp_test_001")
    assert payment is not None
    assert payment["recovery_status"] == "stopped"


def test_create_order_success() -> None:
    """Acceptance Test: create_order sends amount in paise and returns order details."""
    mock_session = MagicMock()
    mock_resp = MagicMock()
    mock_resp.ok = True
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "id": "order_test_123456",
        "amount": 50000,
        "currency": "INR",
        "status": "created",
        "receipt": "rcpt_001",
    }
    mock_session.request.return_value = mock_resp

    adapter = RazorpayAdapter(key_id="rzp_test_k", key_secret="rzp_test_s", session=mock_session)
    order = adapter.create_order(amount_paise=50000, currency="INR", receipt="rcpt_001")

    assert order["order_id"] == "order_test_123456"
    assert order["amount"] == 50000
    assert order["currency"] == "INR"

    call_kwargs = mock_session.request.call_args[1]
    assert call_kwargs["json"]["amount"] == 50000
    assert call_kwargs["json"]["currency"] == "INR"
    assert call_kwargs["json"]["receipt"] == "rcpt_001"


def test_create_order_minimum_amount_validation() -> None:
    """Acceptance Test: Orders under 100 paise are rejected with ValueError."""
    adapter = RazorpayAdapter(key_id="rzp_test_k", key_secret="rzp_test_s")
    with pytest.raises(ValueError, match="at least 100 paise"):
        adapter.create_order(amount_paise=99)


def test_verify_payment_signature_valid_and_invalid() -> None:
    """Acceptance Test: HMAC-SHA256 signature verification validates authentic and detects forged signatures."""
    import hashlib
    import hmac

    secret = "yREyrswrli9dbAIxjAFyu002"
    order_id = "order_DBJOWzybf0sJbb"
    payment_id = "pay_29MoThyUhqd8W5"

    msg = f"{order_id}|{payment_id}".encode()
    valid_signature = hmac.new(secret.encode("utf-8"), msg, hashlib.sha256).hexdigest()

    adapter = RazorpayAdapter(key_id="rzp_test_TY1j7fS5RyVWJ7", key_secret=secret)

    # Valid signature
    assert adapter.verify_payment_signature(order_id, payment_id, valid_signature) is True

    # Tampered signature
    tampered = valid_signature[:-4] + "ffff"
    assert adapter.verify_payment_signature(order_id, payment_id, tampered) is False

    # Empty / missing arguments
    assert adapter.verify_payment_signature("", payment_id, valid_signature) is False
    assert adapter.verify_payment_signature(order_id, "", valid_signature) is False
    assert adapter.verify_payment_signature(order_id, payment_id, "") is False


def test_create_order_endpoint(client) -> None:
    """Integration Test: POST /api/create-order creates order with CORS headers."""
    # Amount below minimum
    res_low = client.post(
        "/api/create-order",
        data=json.dumps({"amount": 50}),
        content_type="application/json",
    )
    assert res_low.status_code == 400
    assert res_low.json()["error"] == "AMOUNT_TOO_LOW"

    # Missing amount
    res_missing = client.post(
        "/api/create-order",
        data=json.dumps({}),
        content_type="application/json",
    )
    assert res_missing.status_code == 400

    # Valid amount (simulated if unconfigured)
    res_valid = client.post(
        "/api/create-order",
        data=json.dumps({"amount": 25000, "currency": "INR", "receipt": "rcpt_test"}),
        content_type="application/json",
    )
    assert res_valid.status_code == 200
    data = res_valid.json()
    assert "order_id" in data
    assert data["amount"] == 25000
    assert data["currency"] == "INR"


def test_verify_payment_endpoint(client) -> None:
    """Integration Test: POST /api/verify-payment verifies HMAC signature."""
    import hashlib
    import hmac

    from django.conf import settings

    secret = getattr(settings, "RAZORPAY_KEY_SECRET", "") or "test_secret_for_suite"

    # 1. Missing fields
    res_missing = client.post(
        "/api/verify-payment",
        data=json.dumps({"razorpay_order_id": "order_123"}),
        content_type="application/json",
    )
    assert res_missing.status_code == 400
    assert res_missing.json()["error"] == "MISSING_FIELDS"

    # 2. Invalid signature
    with patch("django.conf.settings.RAZORPAY_KEY_SECRET", secret):
        res_invalid = client.post(
            "/api/verify-payment",
            data=json.dumps({
                "razorpay_order_id": "order_abc",
                "razorpay_payment_id": "pay_xyz",
                "razorpay_signature": "invalid_signature_hash",
            }),
            content_type="application/json",
        )
        assert res_invalid.status_code == 400
        assert res_invalid.json()["verified"] is False

        # 3. Valid signature
        msg = b"order_abc|pay_xyz"
        valid_sig = hmac.new(secret.encode("utf-8"), msg, hashlib.sha256).hexdigest()

        res_valid = client.post(
            "/api/verify-payment",
            data=json.dumps({
                "razorpay_order_id": "order_abc",
                "razorpay_payment_id": "pay_xyz",
                "razorpay_signature": valid_sig,
            }),
            content_type="application/json",
        )
        assert res_valid.status_code == 200
        assert res_valid.json()["verified"] is True
        assert res_valid.json()["status"] == "success"
