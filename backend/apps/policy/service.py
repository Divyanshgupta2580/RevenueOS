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

        decision_record = {
            "decision_id": decision_id,
            "payment_id": payment_id,
            "model_version": "gemini-2.5-flash",
            "ai_recommendation": ai_recommendation or {},
            "policy_decision": verdict.to_dict(),
            "created_at": now,
        }

        DecisionRepository.create(decision_record)
        return verdict, decision_id
