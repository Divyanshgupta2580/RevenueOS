"""Deterministic policy rule definitions for Guarded Autopilot.

AI recommends. Rules authorize. Only authorized actions can reach execution.
"""

from typing import Any

from apps.core.money import validate_minor_units
from apps.database.repositories import ActionRepository

SUPPORTED_ACTIONS = {"RETRY", "PAYMENT_LINK", "REMINDER", "STOP"}
ALLOWED_ROLES = {"operator", "admin"}
MAX_PERMITTED_AMOUNT_PAISE = 100_000_000  # 10 Lakh INR upper limit safety guard


class PolicyEvaluationResult:
    def __init__(self, passed: bool, rule_name: str, reason: str) -> None:
        self.passed = passed
        self.rule_name = rule_name
        self.reason = reason

    def to_dict(self) -> dict[str, Any]:
        return {
            "ruleName": self.rule_name,
            "rule_name": self.rule_name,
            "passed": self.passed,
            "reason": self.reason,
        }


def check_user_authorization(user: dict[str, Any] | None) -> PolicyEvaluationResult:
    """Rule 1: Operator or admin role is required for recovery action execution."""
    if not user:
        return PolicyEvaluationResult(False, "USER_AUTHORIZATION", "User context is missing or unauthenticated.")

    raw_role = user.get("role", "operator")
    role = str(raw_role).lower().strip()
    if role not in ALLOWED_ROLES:
        return PolicyEvaluationResult(False, "USER_AUTHORIZATION", f"Role '{raw_role}' is not authorized to trigger actions.")

    return PolicyEvaluationResult(True, "USER_AUTHORIZATION", f"User '{user.get('username')}' authorized with role '{raw_role}'.")


def check_supported_action(action: str) -> PolicyEvaluationResult:
    """Rule 2: Action must belong to the strict bounded set."""
    norm_action = action.upper().strip()
    if norm_action not in SUPPORTED_ACTIONS:
        return PolicyEvaluationResult(False, "SUPPORTED_ACTION", f"Action '{action}' is not in supported set {SUPPORTED_ACTIONS}.")
    return PolicyEvaluationResult(True, "SUPPORTED_ACTION", f"Action '{norm_action}' is supported.")


def check_payment_eligibility(payment: dict[str, Any] | None) -> PolicyEvaluationResult:
    """Rule 3: Payment must exist and have an eligible non-terminal status."""
    if not payment:
        return PolicyEvaluationResult(False, "PAYMENT_ELIGIBILITY", "Payment record not found.")

    status = payment.get("status", "").lower()
    if status in ["captured", "paid", "success"]:
        return PolicyEvaluationResult(False, "PAYMENT_ELIGIBILITY", f"Payment is already successfully captured (status: '{status}').")

    if status == "refunded":
        return PolicyEvaluationResult(False, "PAYMENT_ELIGIBILITY", "Payment is refunded; recovery ineligible.")

    return PolicyEvaluationResult(True, "PAYMENT_ELIGIBILITY", f"Payment has eligible status '{status}'.")


def check_already_recovered(payment: dict[str, Any]) -> PolicyEvaluationResult:
    """Rule 4: Opportunity must not already be marked as recovered."""
    recovery_status = payment.get("recovery_status", "pending").lower()
    if recovery_status == "recovered":
        return PolicyEvaluationResult(False, "ALREADY_RECOVERED", "Revenue opportunity is already recovered.")

    return PolicyEvaluationResult(True, "ALREADY_RECOVERED", "Opportunity is active.")


def check_amount_validity(payment: dict[str, Any]) -> PolicyEvaluationResult:
    """Rule 5: Amount must be valid positive integer paise within safety bounds."""
    raw_amount = payment.get("amount")
    if not isinstance(raw_amount, int):
        return PolicyEvaluationResult(False, "AMOUNT_VALIDITY", f"Amount must be integer paise, got {type(raw_amount).__name__}.")

    try:
        amount_paise = validate_minor_units(raw_amount)
    except Exception as exc:
        return PolicyEvaluationResult(False, "AMOUNT_VALIDITY", f"Amount validation failed: {exc}")

    if amount_paise <= 0:
        return PolicyEvaluationResult(False, "AMOUNT_VALIDITY", "Amount must be strictly positive.")

    if amount_paise > MAX_PERMITTED_AMOUNT_PAISE:
        return PolicyEvaluationResult(False, "AMOUNT_VALIDITY", f"Amount ({amount_paise} paise) exceeds safety threshold ({MAX_PERMITTED_AMOUNT_PAISE} paise).")

    return PolicyEvaluationResult(True, "AMOUNT_VALIDITY", f"Amount {amount_paise} paise is valid.")


def check_retry_threshold(payment: dict[str, Any], action: str) -> PolicyEvaluationResult:
    """Rule 6: RETRY action cannot exceed maximum allowed retries."""
    norm_action = action.upper().strip()
    if norm_action != "RETRY":
        return PolicyEvaluationResult(True, "RETRY_THRESHOLD", f"Retry threshold not applicable to action '{norm_action}'.")

    retry_count = int(payment.get("retry_count", 0))
    max_retries = int(payment.get("max_retries_allowed", 3))

    if retry_count >= max_retries:
        return PolicyEvaluationResult(
            False,
            "RETRY_THRESHOLD",
            f"Retry limit reached ({retry_count}/{max_retries}). Subsequent automated retries prohibited."
        )

    return PolicyEvaluationResult(True, "RETRY_THRESHOLD", f"Retry count ({retry_count}/{max_retries}) within limits.")


def check_risk_policy(payment: dict[str, Any], action: str) -> PolicyEvaluationResult:
    """Rule 7: Hard declines and fraud cannot be retried."""
    norm_action = action.upper().strip()
    category = str(payment.get("failure_category") or payment.get("failure_reason") or "unknown").lower()

    if category in ["fraud", "lost_stolen_card", "hard_decline"] and norm_action == "RETRY":
        return PolicyEvaluationResult(
            False,
            "RISK_POLICY",
            f"Action '{norm_action}' strictly prohibited on high-risk decline category '{category}'."
        )

    return PolicyEvaluationResult(True, "RISK_POLICY", "Risk policy checks passed.")


def check_duplicate_execution(idempotency_key: str | None) -> PolicyEvaluationResult:
    """Rule 8: Idempotency key must not have already executed."""
    if not idempotency_key:
        return PolicyEvaluationResult(False, "DUPLICATE_EXECUTION", "Idempotency key is required.")

    existing = ActionRepository.get_by_idempotency_key(idempotency_key)
    if existing:
        return PolicyEvaluationResult(
            False,
            "DUPLICATE_EXECUTION",
            f"Action with idempotency key '{idempotency_key}' has already been executed.",
        )

    return PolicyEvaluationResult(True, "DUPLICATE_EXECUTION", "Action is unique.")
