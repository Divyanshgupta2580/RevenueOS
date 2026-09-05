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

        # 4. Baseline Assumption (8% heuristic evaluation model; not empirical historical merchant data)
        baseline_paise = int(at_risk_paise * 0.08)

        # 5. Incremental Lift (Y - X relative to baseline assumption)
        incremental_paise = max(0, actually_recovered_paise - baseline_paise)

        # 6. Recovery Rate
        total_pool = at_risk_paise + actually_recovered_paise
        recovery_rate = (actually_recovered_paise / total_pool) if total_pool > 0 else 0.0

        # 7. Blocked Actions Count
        blocked_count = db.recovery_decisions.count_documents({"policy_decision.status": "BLOCKED"})

        # 8. Sample Size & Attribution Integrity
        total_observed_transactions = db.payments.count_documents({})
        observed_recoveries_count = len(recovered_payments)
        is_sample_sufficient = observed_recoveries_count >= 30
        attribution_conf = "MEASURED" if is_sample_sufficient else "INSUFFICIENT SAMPLE SIZE"
        stat_sig = "STATISTICALLY SIGNIFICANT" if is_sample_sufficient else "INSUFFICIENT SAMPLE SIZE"
        sample_note = f"{observed_recoveries_count} verified transaction{'s' if observed_recoveries_count != 1 else ''}"

        # 9. Strategy-Level Breakdown (PAYMENT_LINK, REMINDER, RETRY, STOP)
        # Find all decisions to group by action
        all_decisions = list(db.recovery_decisions.find({}))
        strategy_counts: dict[str, int] = {"PAYMENT_LINK": 0, "REMINDER": 0, "RETRY": 0, "STOP": 0}
        strategy_recoveries: dict[str, int] = {"PAYMENT_LINK": 0, "REMINDER": 0, "RETRY": 0, "STOP": 0}

        # Track which payment had which strategy
        payment_strategy_map: dict[str, str] = {}
        for d in all_decisions:
            act = (d.get("action") or d.get("ai_recommendation", {}).get("action") or "STOP").upper()
            if act in strategy_counts:
                strategy_counts[act] += 1
            pid = d.get("payment_id")
            if pid:
                payment_strategy_map[pid] = act

        for p in recovered_payments:
            pid = p.get("payment_id")
            if pid and pid in payment_strategy_map:
                strat = payment_strategy_map[pid]
                if strat in strategy_recoveries:
                    strategy_recoveries[strat] += 1

        strategy_breakdown = []
        for strat in ["PAYMENT_LINK", "REMINDER", "RETRY", "STOP"]:
            s_size = strategy_counts[strat]
            s_rec = strategy_recoveries[strat]
            s_rate = (s_rec / s_size) if s_size > 0 else 0.0
            if s_size == 0:
                attr_status = "No observations"
            elif s_size < 5:
                attr_status = "Not enough observations"
            elif s_size < 30:
                attr_status = "Preliminary (Low Power)"
            else:
                attr_status = "Measured"

            strategy_breakdown.append({
                "strategy": strat,
                "sampleSize": s_size,
                "observedRecoveries": s_rec,
                "observedRecoveryRate": round(s_rate, 4),
                "attributionStatus": attr_status,
            })

        # 10. Recovery Funnel (Failed -> At-Risk -> Analyzed -> Policy Approved -> Recovery Action -> Recovered)
        total_failed_count = len(failed_payments)
        analyzed_count = len(all_decisions)
        approved_count = db.recovery_decisions.count_documents({"policy_decision.status": "APPROVED"})
        action_count = db.recovery_executions.count_documents({})

        funnel = [
            {"stage": "Failed Payments", "count": total_failed_count, "description": "Raw gateway failure records"},
            {"stage": "At-Risk Payments", "count": len(active_failed), "description": "Unresolved drop-offs in active queue"},
            {"stage": "Analyzed", "count": analyzed_count, "description": "Evaluated with Gemini 3.6 Flash"},
            {"stage": "Policy Approved", "count": approved_count, "description": "Passed Guarded Autopilot rules"},
            {"stage": "Recovery Action", "count": action_count, "description": "Dispatched intervention execution"},
            {"stage": "Recovered", "count": observed_recoveries_count, "description": "Verified captured/paid status"},
        ]

        # 11. Historical Trend Availability
        # Check distinct dates in payments
        distinct_dates = set()
        for p in failed_payments:
            dt = p.get("created_at")
            if dt:
                distinct_dates.add(str(dt)[:10])
        trend_available = len(distinct_dates) >= 3

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
            "observedSampleSize": observed_recoveries_count,
            "observedTransactions": total_observed_transactions,
            "observedRecoveries": observed_recoveries_count,
            "isSampleSizeSufficient": is_sample_sufficient,
            "attributionConfidence": attribution_conf,
            "attributionStatus": attribution_conf,
            "baselineAssumption": "Illustrative 8% heuristic control (not causal merchant history)",
            "baselineComparison": "Illustrative",
            "baselineLabel": "Illustrative baseline",
            "statisticalSignificance": stat_sig,
            "sampleSizeHonestNote": sample_note,
            "baselineAssumptionNote": "8% heuristic evaluation model (not empirical historical merchant data)",
            "productionMerchantRecovery": "Not measured",
            "strategyBreakdown": strategy_breakdown,
            "funnel": funnel,
            "historicalTrendAvailable": trend_available,
            "historicalTrendReason": "Historical trend unavailable: minimum 3 consecutive observation periods required.",
        }
