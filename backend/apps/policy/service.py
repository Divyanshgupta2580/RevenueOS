"""Guarded Autopilot Service: Orchestrates policy evaluation and audit ledger persistence."""

import uuid
from datetime import UTC, datetime
from typing import Any

from apps.database.repositories import DecisionRepository, PaymentRepository
from apps.policy.engine import GuardedPolicyEngine, PolicyVerdict


class GuardedAutopilotService:
    """Service mediating between AI recommendations and execution."""

    @classmethod
    def evaluate_and_record(
        cls,
        payment_id: str,
        action: str,
        user: dict[str, Any] | None,
        idempotency_key: str,
        ai_recommendation: dict[str, Any] | None = None,
    ) -> tuple[PolicyVerdict, str]:
        """Evaluate deterministic policy and persist auditable decision ledger record.

        Returns tuple of (PolicyVerdict, decision_id).
        """
        payment = PaymentRepository.get_by_id(payment_id)

        verdict = GuardedPolicyEngine.evaluate(
            payment=payment,
            action=action,
            user=user,
            idempotency_key=idempotency_key,
        )

        decision_id = f"dec_{uuid.uuid4().hex[:12]}"
        now = datetime.now(UTC)

        from apps.brain.config import get_configured_gemini_model
        model_version = get_configured_gemini_model()

        # Build payment snapshot & evidence summary
        payment_snapshot = {}
        evidence_summary = {}
        payment_time_iso = now.isoformat()

        if payment:
            raw_created = payment.get("created_at")
            if raw_created is not None and hasattr(raw_created, "isoformat"):
                payment_time_iso = str(raw_created.isoformat())
            elif raw_created is not None:
                payment_time_iso = str(raw_created)
            else:
                payment_time_iso = now.isoformat()

            payment_snapshot = {
                "paymentId": payment_id,
                "orderId": payment.get("order_id"),
                "customerId": payment.get("customer_id"),
                "customerEmail": payment.get("customer_email"),
                "amount": payment.get("amount", 0),
                "currency": payment.get("currency", "INR"),
                "status": payment.get("status", "failed"),
                "failureCategory": payment.get("failure_category", "soft_decline"),
                "failureReason": payment.get("failure_reason", "unknown"),
                "method": payment.get("method", "card"),
                "retryCount": payment.get("retry_count", 0),
                "maxRetriesAllowed": payment.get("max_retries_allowed", 3),
                "createdAt": payment_time_iso,
            }

            from apps.radar.service import RevenueRadarService

            eval_res = RevenueRadarService.evaluate_opportunity(payment, now=now)
            if eval_res and "evidenceSummary" in eval_res:
                evidence_summary = eval_res["evidenceSummary"]

        # Construct authoritative chronological audit timeline
        timeline = [
            {
                "stage": "FAILURE_DETECTED",
                "title": "Payment Failure Ingested",
                "status": "DETECTED",
                "timestamp": payment_time_iso,
                "details": {
                    "paymentId": payment_id,
                    "failureCategory": payment_snapshot.get("failureCategory", "soft_decline"),
                },
            },
            {
                "stage": "CONTEXT_CONSTRUCTED",
                "title": "Decision Context Envelope Constructed",
                "status": "CONSTRUCTED",
                "timestamp": now.isoformat(),
                "details": {"protocolVersion": "1.0", "endpoint": "recovery.analyze"},
            },
            {
                "stage": "AI_RECOMMENDATION",
                "title": f"Gemini 3.6 Flash Advisory: {action}",
                "status": "RECOMMENDED",
                "timestamp": now.isoformat(),
                "details": {
                    "action": action,
                    "confidence": (ai_recommendation or {}).get("confidence"),
                    "model": model_version,
                },
            },
            {
                "stage": "POLICY_EVALUATION",
                "title": f"Guarded Autopilot Policy Verdict: {verdict.status}",
                "status": verdict.status,
                "timestamp": now.isoformat(),
                "details": {
                    "verdict": verdict.status,
                    "blockingRule": verdict.blocking_rule,
                    "rulesEvaluated": len(verdict.rules_evaluated),
                },
            },
        ]

        exec_status = "BLOCKED" if verdict.status == "BLOCKED" else "PENDING"
        initial_outcome = "BLOCKED_BY_POLICY" if verdict.status == "BLOCKED" else "PENDING"

        decision_record = {
            "decision_id": decision_id,
            "payment_id": payment_id,
            "model_version": model_version,
            "endpoint": "recovery.analyze",
            "request_id": f"req_{decision_id}",
            "payment_snapshot": payment_snapshot,
            "evidence_summary": evidence_summary,
            "ai_recommendation": ai_recommendation or {},
            "policy_decision": verdict.to_dict(),
            "execution_status": exec_status,
            "outcome": initial_outcome,
            "audit_timeline": timeline,
            "created_at": now,
        }

        DecisionRepository.create(decision_record)
        return verdict, decision_id

