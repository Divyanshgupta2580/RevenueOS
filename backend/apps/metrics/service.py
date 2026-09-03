"""Metrics and Outcome Measurement Service.

Computes actual financial recovery performance, deterministic ERV,
and incremental lift compared to unguided baseline controls.
"""

from typing import Any

from apps.core.money import validate_minor_units
from apps.database.client import get_database
from apps.radar.service import RevenueRadarService


class MetricsService:
    """Computes measured recovery performance directly from MongoDB."""

    @classmethod
    def compute_summary(cls) -> dict[str, Any]:
        """Compute top-level KPI metrics in minor currency units (paise)."""
        db = get_database()

        # 1. Total Revenue at Risk (failed, active payments)
        failed_payments = list(db.payments.find({"status": "failed"}))
        active_failed = [p for p in failed_payments if p.get("recovery_status") != "recovered"]
        at_risk_paise = sum(int(p.get("amount", 0)) for p in active_failed)

        # 2. Expected Recoverable Revenue (sum of deterministic ERVs)
        radar_result = RevenueRadarService.rank_opportunities(payments=active_failed, page=1, page_size=100)
        summary = radar_result.get("summary", {})
        expected_recoverable_paise = int(summary.get("expectedRecoverablePaise", 0))
        active_count = int(summary.get("totalOpportunities", len(active_failed)))

        # 3. Actually Recovered Revenue (captured with verified recovery status)
        recovered_payments = list(db.payments.find({
            "status": {"$in": ["captured", "paid"]},
            "recovery_status": "recovered",
        }))
        actually_recovered_paise = sum(int(p.get("amount", 0)) for p in recovered_payments)

        # 4. Baseline Control (Unguided Retry ~8% historical benchmark)
        baseline_paise = int(at_risk_paise * 0.08)

        # 5. Incremental Lift (Y - X)
        incremental_paise = max(0, actually_recovered_paise - baseline_paise)

        # 6. Recovery Rate
        total_pool = at_risk_paise + actually_recovered_paise
        recovery_rate = (actually_recovered_paise / total_pool) if total_pool > 0 else 0.0

        # 7. Blocked Actions Count
        blocked_count = db.recovery_decisions.count_documents({"policy_decision.status": "BLOCKED"})

        # Validate integer minor units
        return {
            "revenueAtRiskPaise": validate_minor_units(at_risk_paise),
            "expectedRecoverablePaise": validate_minor_units(expected_recoverable_paise),
            "actuallyRecoveredPaise": validate_minor_units(actually_recovered_paise),
            "baselineControlPaise": validate_minor_units(baseline_paise),
            "incrementalRevenuePaise": validate_minor_units(incremental_paise),
            "recoveryRate": round(recovery_rate, 4),
            "activeOpportunities": active_count,
            "blockedActions": blocked_count,
        }
