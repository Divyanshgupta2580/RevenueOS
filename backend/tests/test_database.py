"""Acceptance tests for Phase 4: MongoDB Persistence."""

from unittest.mock import MagicMock, patch

import pytest

from apps.database.client import init_database_indexes, ping_database
from apps.database.repositories import (
    ActionRepository,
    DatabaseError,
    DecisionRepository,
    PaymentRepository,
    WebhookEventRepository,
)


def test_ping_database_success() -> None:
    """Acceptance Test: Ping database succeeds when connection is healthy."""
    mock_client = MagicMock()
    mock_client.admin.command.return_value = {"ok": 1}
    with patch("apps.database.client.get_mongo_client", return_value=mock_client):
        assert ping_database() is True


def test_ping_database_failure() -> None:
    """Acceptance Test: Ping database returns False gracefully on connection failure."""
    from pymongo.errors import ConnectionFailure

    mock_client = MagicMock()
    mock_client.admin.command.side_effect = ConnectionFailure("Network timeout")
    with patch("apps.database.client.get_mongo_client", return_value=mock_client):
        assert ping_database() is False


def test_init_database_indexes(mock_db) -> None:
    """Acceptance Test: Indexes are defined across all 6 required collections."""
    indexes = init_database_indexes(mock_db)
    assert "users" in indexes
    assert "sessions" in indexes
    assert "payments" in indexes
    assert "recovery_decisions" in indexes
    assert "recovery_actions" in indexes
    assert "webhook_events" in indexes


def test_payment_repository_create_and_get(mock_db) -> None:
    """Acceptance Test: Payment storage validates integer minor currency units (paise)."""
    payment_data = {
        "payment_id": "pay_test_001",
        "order_id": "order_test_001",
        "customer_id": "cust_test_001",
        "customer_email": "operator@test.com",
        "amount": 499900,  # 4999.00 INR stored as paise
        "currency": "INR",
        "status": "failed",
        "failure_reason": "insufficient_funds",
        "failure_category": "soft_decline",
        "retry_count": 0,
        "max_retries_allowed": 3,
    }

    created = PaymentRepository.create(payment_data)
    assert created["payment_id"] == "pay_test_001"
    assert created["amount"] == 499900
    assert isinstance(created["amount"], int)

    # Bounded lookup
    retrieved = PaymentRepository.get_by_id("pay_test_001")
    assert retrieved is not None
    assert retrieved["amount"] == 499900
    assert "_id" not in retrieved  # Excluded by projection


def test_payment_repository_rejects_floating_point_money(mock_db) -> None:
    """Acceptance Test: Storing floating-point currency is strictly rejected."""
    payment_data = {
        "payment_id": "pay_test_float",
        "amount": 499.90,  # Invalid: Float prohibited
    }
    with pytest.raises(DatabaseError, match="Monetary amount must be an integer minor unit"):
        PaymentRepository.create(payment_data)


def test_payment_repository_duplicate_id_rejected(mock_db) -> None:
    """Acceptance Test: Duplicate payment_id is rejected."""
    payment_data = {
        "payment_id": "pay_test_unique",
        "amount": 10000,
    }
    PaymentRepository.create(payment_data)
    with pytest.raises(DatabaseError, match="already exists"):
        PaymentRepository.create(payment_data)


def test_payment_repository_bounded_pagination(mock_db) -> None:
    """Acceptance Test: Pagination respects bounds and returns count."""
    for i in range(25):
        PaymentRepository.create({
            "payment_id": f"pay_page_{i:02d}",
            "amount": 10000 * (i + 1),
            "status": "failed",
        })

    # Page 1, size 10
    page_1, total = PaymentRepository.list_opportunities(status="failed", page=1, page_size=10)
    assert len(page_1) == 10
    assert total == 25

    # Page 3, size 10
    page_3, _ = PaymentRepository.list_opportunities(status="failed", page=3, page_size=10)
    assert len(page_3) == 5


def test_decision_repository_create_and_get(mock_db) -> None:
    """Acceptance Test: AI recommendations and policy decisions are stored for audit."""
    decision_data = {
        "decision_id": "dec_test_001",
        "payment_id": "pay_test_001",
        "model_version": "gemini-2.0-flash",
        "ai_recommendation": {
            "action": "PAYMENT_LINK",
            "confidence": 0.85,
            "expected_recovery_value_paise": 400000,
        },
        "policy_decision": {
            "status": "APPROVED",
            "authorized_action": "PAYMENT_LINK",
        },
    }
    created = DecisionRepository.create(decision_data)
    assert created["decision_id"] == "dec_test_001"

    retrieved = DecisionRepository.get_by_id("dec_test_001")
    assert retrieved is not None
    assert retrieved["ai_recommendation"]["action"] == "PAYMENT_LINK"


def test_action_repository_enforces_idempotency(mock_db) -> None:
    """Acceptance Test: Duplicate action idempotency keys are strictly rejected."""
    action_data = {
        "action_id": "act_test_001",
        "decision_id": "dec_test_001",
        "payment_id": "pay_test_001",
        "action_type": "PAYMENT_LINK",
        "idempotency_key": "idemp_pay_001_plink_1",
    }
    ActionRepository.create(action_data)

    duplicate_action = {
        "action_id": "act_test_002",
        "decision_id": "dec_test_001",
        "payment_id": "pay_test_001",
        "action_type": "PAYMENT_LINK",
        "idempotency_key": "idemp_pay_001_plink_1",  # Same idempotency key
    }
    with pytest.raises(DatabaseError, match="already exists"):
        ActionRepository.create(duplicate_action)


def test_webhook_event_repository_idempotency(mock_db) -> None:
    """Acceptance Test: Webhook events are processed exactly once."""
    event_data = {
        "event_id": "evt_rzp_test_001",
        "event_type": "payment_link.paid",
        "payment_id": "pay_test_001",
    }
    assert WebhookEventRepository.is_processed("evt_rzp_test_001") is False

    WebhookEventRepository.record_event(event_data)
    assert WebhookEventRepository.is_processed("evt_rzp_test_001") is True

    # Duplicate recording rejected
    with pytest.raises(DatabaseError, match="already recorded"):
        WebhookEventRepository.record_event(event_data)


def test_zero_startup_dummy_data(mock_db) -> None:
    """Acceptance Test: Absolute zero dummy data policy (fresh system has 0 records)."""
    opps, total = PaymentRepository.list_opportunities()
    assert len(opps) == 0
    assert total == 0
