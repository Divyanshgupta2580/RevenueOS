"""Phase 5 Outcome Metrics and Scientific Honesty Tests.

Validates that MetricsService computes real, deterministic recovery outcomes
with strict sample size honesty, integer paise precision, truthful strategy
breakdowns, and accurate recovery funnels.
"""

from unittest.mock import MagicMock, patch

import pytest

from apps.metrics.service import MetricsService


@pytest.fixture
def mock_empty_db():
    """Mock MongoDB with 0 transactions."""
    mock_db = MagicMock()
    mock_db.payments.find.return_value = []
    mock_db.payments.count_documents.return_value = 0
    mock_db.recovery_decisions.find.return_value = []
    mock_db.recovery_decisions.count_documents.return_value = 0
    mock_db.recovery_executions.count_documents.return_value = 0
    return mock_db


@pytest.fixture
def mock_single_transaction_db():
    """Mock MongoDB with 1 real failed payment (pay_TY6cS8vkYS9cWn) and 1 blocked decision."""
    mock_db = MagicMock()
    failed_payment = {
        "payment_id": "pay_TY6cS8vkYS9cWn",
        "amount": 150000,
        "currency": "INR",
        "status": "failed",
        "failure_category": "soft_decline",
        "failure_reason": "international_transaction_not_allowed",
        "recovery_status": "at_risk",
        "created_at": "2026-09-04T21:19:54.523Z",
    }
    decision = {
        "decision_id": "dec_d907c8a43bff",
        "payment_id": "pay_TY6cS8vkYS9cWn",
        "action": "PAYMENT_LINK",
        "policy_decision": {"status": "BLOCKED"},
    }

    def payments_find(query):
        status = query.get("status")
        if status == "failed":
            return [failed_payment]
        if isinstance(status, dict) and "$in" in status:
            return []  # No recovered payments yet
        return [failed_payment]

    mock_db.payments.find.side_effect = payments_find
    mock_db.payments.count_documents.side_effect = lambda q: 1 if q == {} or q.get("status") == "failed" else 0
    mock_db.recovery_decisions.find.return_value = [decision]
    mock_db.recovery_decisions.count_documents.side_effect = lambda q: 1 if q.get("policy_decision.status") == "BLOCKED" else 0
    mock_db.recovery_executions.count_documents.return_value = 0
    return mock_db


def test_zero_transactions_metrics(mock_empty_db):
    """Zero transactions produces truthful zeroes and honest sample size caveat."""
    with patch("apps.metrics.service.get_database", return_value=mock_empty_db):
        summary = MetricsService.compute_summary()

        assert summary["revenueAtRiskPaise"] == 0
        assert summary["expectedRecoverablePaise"] == 0
        assert summary["actuallyRecoveredPaise"] == 0
        assert summary["baselineControlPaise"] == 0
        assert summary["incrementalRevenuePaise"] == 0
        assert summary["recoveryRate"] == 0.0
        assert summary["observedTransactions"] == 0
        assert summary["observedRecoveries"] == 0
        assert summary["isSampleSizeSufficient"] is False
        assert summary["attributionStatus"] == "INSUFFICIENT SAMPLE SIZE"
        assert summary["historicalTrendAvailable"] is False


def test_one_transaction_scientific_honesty(mock_single_transaction_db):
    """One transaction reflects exact integer amounts and insufficient sample disclaimer."""
    with patch("apps.metrics.service.get_database", return_value=mock_single_transaction_db):
        summary = MetricsService.compute_summary()

        assert summary["revenueAtRiskPaise"] == 150000
        assert isinstance(summary["revenueAtRiskPaise"], int)
        assert summary["actuallyRecoveredPaise"] == 0
        assert summary["baselineControlPaise"] == 12000  # 8% of 150000 = 12000 paise
        assert summary["incrementalRevenuePaise"] == 0
        assert summary["recoveryRate"] == 0.0

        # Evidence Context
        assert summary["observedTransactions"] == 1
        assert summary["observedRecoveries"] == 0
        assert summary["isSampleSizeSufficient"] is False
        assert summary["attributionStatus"] == "INSUFFICIENT SAMPLE SIZE"
        assert summary["baselineComparison"] == "Illustrative"

        # Strategy breakdown
        breakdown = {s["strategy"]: s for s in summary["strategyBreakdown"]}
        assert breakdown["PAYMENT_LINK"]["sampleSize"] == 1
        assert breakdown["PAYMENT_LINK"]["observedRecoveries"] == 0
        assert breakdown["PAYMENT_LINK"]["attributionStatus"] == "Not enough observations"

        assert breakdown["REMINDER"]["sampleSize"] == 0
        assert breakdown["REMINDER"]["attributionStatus"] == "No observations"

        # Funnel
        funnel = {f["stage"]: f["count"] for f in summary["funnel"]}
        assert funnel["Failed Payments"] == 1
        assert funnel["At-Risk Payments"] == 1
        assert funnel["Analyzed"] == 1
        assert funnel["Policy Approved"] == 0
        assert funnel["Recovery Action"] == 0
        assert funnel["Recovered"] == 0


def test_multiple_transactions_and_strategies():
    """Multiple transactions across strategies compute correct proportions without floating point."""
    mock_db = MagicMock()
    failed_1 = {"payment_id": "p1", "amount": 100000, "status": "failed", "recovery_status": "recovered"}
    failed_2 = {"payment_id": "p2", "amount": 200000, "status": "failed", "recovery_status": "at_risk"}
    rec_1 = {"payment_id": "p1", "amount": 100000, "status": "captured", "recovery_status": "recovered"}

    dec_1 = {"decision_id": "d1", "payment_id": "p1", "action": "PAYMENT_LINK", "policy_decision": {"status": "APPROVED"}}
    dec_2 = {"decision_id": "d2", "payment_id": "p2", "action": "REMINDER", "policy_decision": {"status": "APPROVED"}}

    def payments_find(query):
        status = query.get("status")
        if status == "failed":
            return [failed_1, failed_2]
        if isinstance(status, dict) and "$in" in status:
            return [rec_1]
        return [failed_1, failed_2, rec_1]

    mock_db.payments.find.side_effect = payments_find
    mock_db.payments.count_documents.return_value = 3
    mock_db.recovery_decisions.find.return_value = [dec_1, dec_2]
    mock_db.recovery_decisions.count_documents.side_effect = lambda q: 2 if q.get("policy_decision.status") == "APPROVED" else 0
    mock_db.recovery_executions.count_documents.return_value = 1

    with patch("apps.metrics.service.get_database", return_value=mock_db):
        summary = MetricsService.compute_summary()

        # At risk is only unrecovered failed payments = 200000
        assert summary["revenueAtRiskPaise"] == 200000
        assert summary["actuallyRecoveredPaise"] == 100000
        assert summary["baselineControlPaise"] == 16000  # 8% of 200000
        assert summary["incrementalRevenuePaise"] == 100000 - 16000  # 84000 paise
        assert isinstance(summary["incrementalRevenuePaise"], int)

        # Recovery rate = 100000 / (200000 + 100000) = 1/3 = 0.3333
        assert summary["recoveryRate"] == 0.3333

        # Strategy breakdown
        breakdown = {s["strategy"]: s for s in summary["strategyBreakdown"]}
        assert breakdown["PAYMENT_LINK"]["sampleSize"] == 1
        assert breakdown["PAYMENT_LINK"]["observedRecoveries"] == 1
        assert breakdown["PAYMENT_LINK"]["observedRecoveryRate"] == 1.0

        assert breakdown["REMINDER"]["sampleSize"] == 1
        assert breakdown["REMINDER"]["observedRecoveries"] == 0
        assert breakdown["REMINDER"]["observedRecoveryRate"] == 0.0


def test_integer_paise_integrity():
    """Verify that all monetary fields strictly pass integer minor unit validation."""
    mock_db = MagicMock()
    mock_db.payments.find.return_value = [{"payment_id": "p_int", "amount": 99999, "status": "failed", "recovery_status": "at_risk"}]
    mock_db.payments.count_documents.return_value = 1
    mock_db.recovery_decisions.find.return_value = []
    mock_db.recovery_decisions.count_documents.return_value = 0
    mock_db.recovery_executions.count_documents.return_value = 0

    with patch("apps.metrics.service.get_database", return_value=mock_db):
        summary = MetricsService.compute_summary()

        for field in ["revenueAtRiskPaise", "expectedRecoverablePaise", "actuallyRecoveredPaise", "baselineControlPaise", "incrementalRevenuePaise"]:
            val = summary[field]
            assert isinstance(val, int), f"{field} is not int: {type(val)}"
            assert val >= 0, f"{field} is negative: {val}"
