"""Test suite verifying Metric Integrity, Integer Minor Units, and Honest Sample-Size Semantics.

Ensures:
- All monetary metrics remain integer minor units (paise).
- Estimated Lift does not claim statistically proven causal impact when sample size is tiny.
- Honest metadata (sample size, illustrative baseline, attribution confidence) is exposed.
- Zero secrets or internal credentials appear in metric responses.
"""

from unittest.mock import MagicMock, patch

from apps.metrics.service import MetricsService


def test_metrics_summary_integer_minor_units():
    """All monetary metrics must be integer paise; zero floating point currency."""
    mock_db = MagicMock()
    mock_db.payments.find.side_effect = [
        # active failed
        [
            {"payment_id": "p1", "amount": 100000, "status": "failed", "recovery_status": "pending"},
            {"payment_id": "p2", "amount": 250000, "status": "failed", "recovery_status": "pending"},
        ],
        # recovered
        [
            {"payment_id": "p3", "amount": 70100, "status": "captured", "recovery_status": "recovered"},
        ],
    ]
    mock_db.recovery_decisions.count_documents.return_value = 2

    with patch("apps.metrics.service.get_database", return_value=mock_db):
        summary = MetricsService.compute_summary()

    # Verify integer types
    assert isinstance(summary["revenueAtRiskPaise"], int)
    assert isinstance(summary["expectedRecoverablePaise"], int)
    assert isinstance(summary["actuallyRecoveredPaise"], int)
    assert isinstance(summary["baselineControlPaise"], int)
    assert isinstance(summary["incrementalRevenuePaise"], int)

    # Specific values
    assert summary["revenueAtRiskPaise"] == 350000
    assert summary["actuallyRecoveredPaise"] == 70100
    assert summary["baselineControlPaise"] == int(350000 * 0.08)


def test_metrics_small_sample_size_semantics():
    """When sample size is tiny (e.g. 1 transaction), attribution confidence must be INSUFFICIENT SAMPLE SIZE."""
    mock_db = MagicMock()
    mock_db.payments.find.side_effect = [
        # active failed
        [{"payment_id": "p1", "amount": 100000, "status": "failed", "recovery_status": "pending"}],
        # recovered: 1 transaction
        [{"payment_id": "p2", "amount": 70100, "status": "captured", "recovery_status": "recovered"}],
    ]
    mock_db.recovery_decisions.count_documents.return_value = 1

    with patch("apps.metrics.service.get_database", return_value=mock_db):
        summary = MetricsService.compute_summary()

    assert summary["observedSampleSize"] == 1
    assert summary["attributionConfidence"] == "INSUFFICIENT SAMPLE SIZE"
    assert summary["statisticalSignificance"] == "INSUFFICIENT SAMPLE SIZE"
    assert summary["baselineComparison"] == "Illustrative"
    assert "1 verified transaction" in summary["sampleSizeHonestNote"]


def test_metrics_no_secrets_exposed():
    """Metric summaries must contain zero keys, tokens, or credential fields."""
    mock_db = MagicMock()
    mock_db.payments.find.side_effect = [[], []]
    mock_db.recovery_decisions.count_documents.return_value = 0

    with patch("apps.metrics.service.get_database", return_value=mock_db):
        summary = MetricsService.compute_summary()

    summary_str = str(summary).lower()
    for forbidden in ["key_secret", "api_key", "password", "token", "auth"]:
        assert forbidden not in summary_str
