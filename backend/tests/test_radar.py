"""Acceptance tests for Phase 5: Revenue Radar & Deterministic ERV."""

import json
from datetime import UTC, datetime, timedelta

import pytest

from apps.database.repositories import PaymentRepository
from apps.radar.scoring import (
    compute_age_multiplier,
    compute_failure_multiplier,
    compute_opportunity_erv,
    compute_recoverability_score,
    compute_retry_multiplier,
)
from apps.radar.service import RevenueRadarService
from apps.websocket.consumer import RevenueOSConsumer
from tests.test_websocket import WebsocketTestCommunicator


def test_failure_multiplier_taxonomy() -> None:
    """Acceptance Test: Failure category multipliers follow deterministic taxonomy."""
    assert compute_failure_multiplier("network_timeout") == 1.00
    assert compute_failure_multiplier("gateway_error") == 0.95
    assert compute_failure_multiplier("soft_decline") == 0.75
    assert compute_failure_multiplier("insufficient_funds") == 0.70
    assert compute_failure_multiplier("hard_decline") == 0.05
    assert compute_failure_multiplier("fraud") == 0.00
    assert compute_failure_multiplier("non_existent_code") == 0.40  # Default unknown


def test_retry_decay_multiplier() -> None:
    """Acceptance Test: Retry decay degrades score deterministically with each attempt."""
    assert compute_retry_multiplier(0, 3) == 1.00
    assert compute_retry_multiplier(1, 3) == 0.6667
    assert compute_retry_multiplier(2, 3) == 0.3333
    assert compute_retry_multiplier(3, 3) == 0.00
    assert compute_retry_multiplier(5, 3) == 0.00  # Strictly bounded at 0.00


def test_age_decay_multiplier() -> None:
    """Acceptance Test: Age decay degrades score deterministically based on hours elapsed."""
    now = datetime(2026, 9, 3, 12, 0, 0, tzinfo=UTC)

    # 30 minutes old
    t_30m = now - timedelta(minutes=30)
    assert compute_age_multiplier(t_30m, now=now) == 1.00

    # 3 hours old
    t_3h = now - timedelta(hours=3)
    assert compute_age_multiplier(t_3h, now=now) == 0.85

    # 12 hours old
    t_12h = now - timedelta(hours=12)
    assert compute_age_multiplier(t_12h, now=now) == 0.60

    # 48 hours old
    t_48h = now - timedelta(hours=48)
    assert compute_age_multiplier(t_48h, now=now) == 0.35

    # 5 days old
    t_5d = now - timedelta(days=5)
    assert compute_age_multiplier(t_5d, now=now) == 0.10


def test_recoverability_score_bounds() -> None:
    """Acceptance Test: Score is strictly bounded between 0 and 100."""
    now = datetime(2026, 9, 3, 12, 0, 0, tzinfo=UTC)

    # Ideal payment: network timeout, 0 retries, brand new, perfect history
    best_payment = {
        "failure_category": "network_timeout",
        "retry_count": 0,
        "created_at": now,
        "customer_history_score": 1.0,
    }
    score_best = compute_recoverability_score(best_payment, now=now)
    assert 95 <= score_best <= 100

    # Worst payment: fraud, 3 retries, 10 days old, bad history
    worst_payment = {
        "failure_category": "fraud",
        "retry_count": 3,
        "created_at": now - timedelta(days=10),
        "customer_history_score": 0.0,
    }
    score_worst = compute_recoverability_score(worst_payment, now=now)
    assert 0 <= score_worst <= 5


def test_expected_recovery_value_integer_paise() -> None:
    """Acceptance Test: ERV produces integer paise and prevents floating point drift."""
    amount_paise = 1500000  # 15,000 INR
    score = 80
    category = "soft_decline"

    erv_paise, action, p_act = compute_opportunity_erv(amount_paise, score, category)
    assert isinstance(erv_paise, int)
    assert action == "PAYMENT_LINK"
    assert p_act == 0.75

    # Expected: floor(1500000 * 0.80 * 0.75) = floor(900000) = 900000 paise (9,000 INR)
    assert erv_paise == 900000


def test_ranking_reproducible_and_prioritized() -> None:
    """Acceptance Test: Opportunities are sorted deterministically by ERV then score."""
    now = datetime(2026, 9, 3, 12, 0, 0, tzinfo=UTC)

    # High amount, low recoverability
    p1 = {
        "payment_id": "pay_large_hard",
        "amount": 10000000,  # 100,000 INR
        "failure_category": "hard_decline",
        "retry_count": 2,
        "created_at": now - timedelta(hours=10),
    }

    # Medium amount, very high recoverability
    p2 = {
        "payment_id": "pay_med_transient",
        "amount": 5000000,  # 50,000 INR
        "failure_category": "network_timeout",
        "retry_count": 0,
        "created_at": now - timedelta(minutes=15),
    }

    ranked = RevenueRadarService.rank_opportunities([p1, p2], now=now)
    opps = ranked["opportunities"]

    # p2 has higher ERV than p1 despite lower nominal amount
    assert opps[0]["paymentId"] == "pay_med_transient"
    assert opps[0]["priorityRank"] == 1
    assert opps[1]["paymentId"] == "pay_large_hard"
    assert opps[1]["priorityRank"] == 2


def test_empty_dataset_handling() -> None:
    """Acceptance Test: Empty dataset returns structured zero-state without error."""
    result = RevenueRadarService.rank_opportunities([])
    assert result["opportunities"] == []
    assert result["pagination"]["total"] == 0
    assert result["summary"]["totalOpportunities"] == 0
    assert result["summary"]["revenueAtRiskPaise"] == 0
    assert result["summary"]["expectedRecoverablePaise"] == 0


def test_invalid_records_rejected_gracefully() -> None:
    """Acceptance Test: Corrupted records are skipped without crashing evaluation loop."""
    invalid_payment = {"payment_id": "pay_corrupt", "amount": "NOT_AN_INT"}
    valid_payment = {"payment_id": "pay_valid", "amount": 10000, "failure_category": "soft_decline"}

    result = RevenueRadarService.rank_opportunities([invalid_payment, valid_payment])
    assert len(result["opportunities"]) == 1
    assert result["opportunities"][0]["paymentId"] == "pay_valid"


@pytest.mark.asyncio
async def test_websocket_revenue_list_integration(mock_db) -> None:
    """Acceptance Test: Live WebSocket revenue.list returns ranked radar opportunities."""
    # Seed one valid payment in mock DB
    PaymentRepository.create({
        "payment_id": "pay_ws_radar_001",
        "amount": 250000,  # 2,500 INR
        "status": "failed",
        "failure_category": "insufficient_funds",
        "retry_count": 0,
    })

    user = {"id": "usr_test", "username": "operator"}
    communicator = WebsocketTestCommunicator(RevenueOSConsumer.as_asgi(), user=user)
    await communicator.connect()

    list_frame = {
        "protocolVersion": "v1",
        "requestId": "req_radar_ws",
        "type": "revenue.list",
        "payload": {"page": 1, "pageSize": 10},
    }
    await communicator.send_to(text_data=json.dumps(list_frame))

    response = json.loads(await communicator.receive_from())
    assert response["type"] == "revenue.list.response"
    assert response["requestId"] == "req_radar_ws"

    opps = response["payload"]["opportunities"]
    assert len(opps) == 1
    assert opps[0]["paymentId"] == "pay_ws_radar_001"
    assert opps[0]["amountPaise"] == 250000
    assert opps[0]["expectedRecoveryValuePaise"] > 0
    assert opps[0]["priorityRank"] == 1

    await communicator.disconnect()
