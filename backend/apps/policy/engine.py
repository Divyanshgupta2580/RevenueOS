"""Guarded Policy Engine: Evaluates AI recommendations against deterministic business rules."""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal

from apps.policy.rules import (
    PolicyEvaluationResult,
    check_already_recovered,
    check_amount_validity,
    check_duplicate_execution,
    check_payment_eligibility,
    check_retry_threshold,
    check_risk_policy,
    check_supported_action,
    check_user_authorization,
)


@dataclass
class PolicyVerdict:
    """Immutable audit verdict produced by the policy engine."""
    status: Literal["APPROVED", "BLOCKED"]
    authorized_action: str | None
    rules_evaluated: list[dict[str, Any]] = field(default_factory=list)
    blocking_rule: str | None = None
    blocking_reason: str | None = None
    evaluated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "authorizedAction": self.authorized_action,
            "blockingRule": self.blocking_rule,
            "blockingReason": self.blocking_reason,
            "rulesEvaluated": self.rules_evaluated,
            "evaluatedAt": self.evaluated_at.isoformat(),
        }


class GuardedPolicyEngine:
    """Deterministic policy engine gating all recovery execution.

    AI recommends. Rules authorize.
    """

    @classmethod
    def evaluate(
        cls,
        payment: dict[str, Any] | None,
        action: str,
        user: dict[str, Any] | None,
        idempotency_key: str,
    ) -> PolicyVerdict:
        """Run all deterministic policy rules in strict sequence.

        Evaluation short-circuits to BLOCKED upon the first failing rule.
        """
        rules_evaluated: list[dict[str, Any]] = []
        first_blocking_rule: str | None = None
        first_blocking_reason: str | None = None

        # Sequence of checks
        checks: list[tuple[str, PolicyEvaluationResult]] = [
            ("USER_AUTHORIZATION", check_user_authorization(user)),
            ("SUPPORTED_ACTION", check_supported_action(action)),
            ("PAYMENT_ELIGIBILITY", check_payment_eligibility(payment)),
        ]

        for rule_name, res in checks:
            rules_evaluated.append(res.to_dict())
            if not res.passed and first_blocking_rule is None:
                first_blocking_rule = rule_name
                first_blocking_reason = res.reason

        if payment is not None:
            subsequent_checks: list[tuple[str, PolicyEvaluationResult]] = [
                ("ALREADY_RECOVERED", check_already_recovered(payment)),
                ("AMOUNT_VALIDITY", check_amount_validity(payment)),
                ("RETRY_THRESHOLD", check_retry_threshold(payment, action)),
                ("RISK_POLICY", check_risk_policy(payment, action)),
                ("DUPLICATE_EXECUTION", check_duplicate_execution(idempotency_key)),
            ]

            for rule_name, res in subsequent_checks:
                rules_evaluated.append(res.to_dict())
                if not res.passed and first_blocking_rule is None:
                    first_blocking_rule = rule_name
                    first_blocking_reason = res.reason
        else:
            for unev in ["ALREADY_RECOVERED", "AMOUNT_VALIDITY", "RETRY_THRESHOLD", "RISK_POLICY", "DUPLICATE_EXECUTION"]:
                rules_evaluated.append({
                    "ruleName": unev,
                    "passed": False,
                    "reason": "Payment record required for evaluation."
                })

        if first_blocking_rule is not None:
            return PolicyVerdict(
                status="BLOCKED",
                authorized_action=None,
                rules_evaluated=rules_evaluated,
                blocking_rule=first_blocking_rule,
                blocking_reason=first_blocking_reason,
            )

        # All deterministic rules passed: action is authorized
        return PolicyVerdict(
            status="APPROVED",
            authorized_action=action.upper().strip(),
            rules_evaluated=rules_evaluated,
            blocking_rule=None,
            blocking_reason=None,
        )
