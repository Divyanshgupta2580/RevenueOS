"""Revenue Radar Service: Opportunity Evaluation, Ranking, and Summary.

Orchestrates deterministic financial calculations without LLM dependency.
"""

import logging
from datetime import UTC, datetime
from typing import Any

from apps.core.money import format_paise_to_inr_string, validate_minor_units
from apps.radar.scoring import (
    compute_age_multiplier,
    compute_customer_history_multiplier,
    compute_failure_multiplier,
    compute_opportunity_erv,
    compute_recoverability_score,
    compute_retry_multiplier,
)

logger = logging.getLogger("revenueos.radar")


class RevenueRadarService:
    """Service for evaluating and prioritizing revenue-at-risk opportunities."""

    @classmethod
    def evaluate_opportunity(
        cls,
        payment: dict[str, Any],
        now: datetime | None = None,
    ) -> dict[str, Any] | None:
        """Evaluate a single payment into a structured Revenue Recovery Opportunity.

        Returns None if payment is invalid or has non-integer paise amount.
        """
        payment_id = payment.get("payment_id")
        if not payment_id:
            return None

        raw_amount = payment.get("amount")
        if not isinstance(raw_amount, int):
            logger.warning(f"Payment {payment_id} rejected by Radar: amount not integer paise ({raw_amount})")
            return None

        try:
            amount_paise = validate_minor_units(raw_amount)
        except Exception:
            return None

        if now is None:
            now = datetime.now(UTC)

        score = compute_recoverability_score(payment, now=now)
        category = str(payment.get("failure_category") or payment.get("failure_reason") or "unknown")
        erv_paise, action, action_p = compute_opportunity_erv(amount_paise, score, category)

        # Audit factors explaining why this score was produced
        retry_count = int(payment.get("retry_count", 0))
        max_retries = int(payment.get("max_retries_allowed", 3))

        factors = {
            "failureCategory": category,
            "categoryMultiplier": compute_failure_multiplier(category),
            "retryCount": retry_count,
            "maxRetries": max_retries,
            "retryMultiplier": compute_retry_multiplier(retry_count, max_retries),
            "ageMultiplier": compute_age_multiplier(payment.get("created_at"), now=now),
            "customerMultiplier": compute_customer_history_multiplier(payment.get("customer_history_score")),
            "actionProbability": action_p,
        }

        # Privacy-safe masked customer display
        cust_email = payment.get("customer_email")
        cust_id = payment.get("customer_id")
        if cust_email and "@" in str(cust_email):
            parts = str(cust_email).split("@", 1)
            name, domain = parts[0], parts[1]
            masked_name = name[:2] + "***" if len(name) > 2 else name[:1] + "***"
            customer_masked = f"{masked_name}@{domain}"
        elif cust_id:
            c_str = str(cust_id)
            customer_masked = c_str[:4] + "..." + c_str[-3:] if len(c_str) > 7 else c_str
        else:
            customer_masked = "Anonymous"

        # Payment age
        created_at_raw = payment.get("created_at")
        if isinstance(created_at_raw, datetime):
            age_sec = max(0, int((now - created_at_raw).total_seconds()))
        else:
            age_sec = 0

        if age_sec < 60:
            payment_age = f"{age_sec}s ago"
        elif age_sec < 3600:
            payment_age = f"{age_sec // 60}m ago"
        elif age_sec < 86400:
            payment_age = f"{age_sec // 3600}h ago"
        else:
            payment_age = f"{age_sec // 86400}d ago"

        # Deterministic Priority
        if score >= 70:
            priority = "HIGH"
        elif score >= 40:
            priority = "MEDIUM"
        else:
            priority = "LOW"

        # Next eligible action & Deterministic Policy Status
        rec_status = str(payment.get("recovery_status", "pending"))
        is_terminal = category in ["fraud", "lost_stolen_card", "card_expired", "account_closed"]
        if is_terminal or retry_count >= max_retries or rec_status in ["recovered", "abandoned"]:
            next_action = "STOP"
        else:
            next_action = action

        from apps.policy.engine import GuardedPolicyEngine
        candidate_action = next_action if next_action in ["RETRY", "PAYMENT_LINK", "REMINDER"] else "PAYMENT_LINK"
        preview_verdict = GuardedPolicyEngine.evaluate(
            payment=payment,
            action=candidate_action,
            user={"id": "operator", "username": "operator", "role": "operator"},
            idempotency_key=f"preview_{payment_id}_{candidate_action}",
        )

        if preview_verdict.status == "BLOCKED":
            policy_status = "BLOCKED"
            policy_reason = preview_verdict.blocking_reason or "Blocked by policy"
        else:
            policy_status = "APPROVED"
            policy_reason = f"Action {action} conforms to merchant recovery limits"

        return {
            "paymentId": payment_id,
            "orderId": payment.get("order_id"),
            "customerId": payment.get("customer_id"),
            "customerEmail": payment.get("customer_email"),
            "customerMasked": customer_masked,
            "amountPaise": amount_paise,
            "formattedAmount": format_paise_to_inr_string(amount_paise),
            "currency": payment.get("currency", "INR"),
            "status": payment.get("status", "failed"),
            "recoveryStatus": rec_status,
            "failureCategory": category,
            "failureReason": str(payment.get("failure_reason") or category),
            "retryCount": retry_count,
            "maxRetries": max_retries,
            "paymentAge": payment_age,
            "recoverabilityScore": score,
            "expectedRecoveryValuePaise": erv_paise,
            "formattedERV": format_paise_to_inr_string(erv_paise),
            "recommendedIntervention": payment.get("ai_recommended_action") or action,
            "heuristicRecommendedAction": action,
            "aiConfidence": payment.get("ai_confidence"),
            "lastAction": payment.get("last_recovery_action", "NONE"),
            "nextEligibleAction": next_action,
            "policyStatus": policy_status,
            "policyReason": policy_reason,
            "priority": priority,
            "factors": factors,
            "policyVerdict": preview_verdict.to_dict(),
            "rulesEvaluated": preview_verdict.rules_evaluated,
            "evidenceSummary": {
                "verifiedFacts": {
                    "status": str(payment.get("status", "failed")).upper(),
                    "amount": format_paise_to_inr_string(amount_paise),
                    "currency": payment.get("currency", "INR"),
                    "failureCategory": category,
                    "failureReason": str(payment.get("failure_reason") or category),
                    "paymentMethod": str(payment.get("method") or "card"),
                    "captured": bool(payment.get("captured", False)),
                },
                "backendCalculations": {
                    "recoverabilityScore": score,
                    "expectedRecoveryPaise": erv_paise,
                    "formattedERV": format_paise_to_inr_string(erv_paise),
                    "estimatedProbability": round(score / 100.0, 2),
                    "paymentAge": payment_age,
                },
                "historicalEvidence": {
                    "customerId": customer_masked,
                    "customerSuccessfulPayments": 0,
                    "customerFailedPayments": 1,
                    "recoveryAttempts": retry_count,
                },
                "policyConstraints": {
                    "maxRetries": max_retries,
                    "cooldownSeconds": 300,
                    "allowedActions": ["RETRY", "PAYMENT_LINK", "REMINDER", "STOP"],
                    "maxAmountPaise": 100_000_000,
                },
                "systemState": {
                    "isTestMode": True,
                    "duplicateProtectionActive": True,
                    "paymentLinkApiAvailable": True,
                    "simulatedRetryAvailable": True,
                },
            },
            "createdAt": payment.get("created_at", now).isoformat() if hasattr(payment.get("created_at"), "isoformat") else str(payment.get("created_at")),
            "updatedAt": payment.get("updated_at", now).isoformat() if hasattr(payment.get("updated_at"), "isoformat") else str(payment.get("updated_at")),
        }

    @classmethod
    def rank_opportunities(
        cls,
        payments: list[dict[str, Any]],
        page: int = 1,
        page_size: int = 20,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        """Rank opportunities deterministically by ERV, then score, then paymentId.

        Gracefully handles empty datasets and invalid records without crashing.
        """
        evaluated: list[dict[str, Any]] = []
        total_risk_paise = 0
        total_erv_paise = 0

        if now is None:
            now = datetime.now(UTC)

        for p in payments:
            opp = cls.evaluate_opportunity(p, now=now)
            if opp is not None:
                evaluated.append(opp)
                total_risk_paise += opp["amountPaise"]
                total_erv_paise += opp["expectedRecoveryValuePaise"]

        # Deterministic sorting: Highest ERV first, then highest score, then paymentId
        evaluated.sort(
            key=lambda o: (
                -o["expectedRecoveryValuePaise"],
                -o["recoverabilityScore"],
                o["paymentId"],
            )
        )

        # Pagination
        bounded_size = min(max(1, page_size), 100)
        total_count = len(evaluated)
        skip = (max(1, page) - 1) * bounded_size
        page_items = evaluated[skip : skip + bounded_size]

        # Priority ranks assigned to paginated items
        for idx, item in enumerate(page_items):
            item["priorityRank"] = skip + idx + 1

        avg_score = (
            round(sum(o["recoverabilityScore"] for o in evaluated) / total_count, 1)
            if total_count > 0
            else 0.0
        )

        return {
            "opportunities": page_items,
            "pagination": {
                "page": page,
                "pageSize": bounded_size,
                "total": total_count,
                "totalPages": (total_count + bounded_size - 1) // bounded_size if total_count > 0 else 0,
            },
            "summary": {
                "totalOpportunities": total_count,
                "revenueAtRiskPaise": total_risk_paise,
                "formattedRevenueAtRisk": format_paise_to_inr_string(total_risk_paise),
                "expectedRecoverablePaise": total_erv_paise,
                "formattedExpectedRecoverable": format_paise_to_inr_string(total_erv_paise),
                "averageRecoverabilityScore": avg_score,
            },
        }
