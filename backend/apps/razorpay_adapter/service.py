"""Razorpay Recovery Executor: Executes authorized actions and records immutable audit actions."""

import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from apps.database.repositories import ActionRepository, PaymentRepository
from apps.razorpay_adapter.adapter import RazorpayAdapter
from apps.razorpay_adapter.exceptions import RazorpayError

logger = logging.getLogger("revenueos.razorpay")


class RazorpayRecoveryExecutor:
    """Orchestrates execution of authorized recovery actions in Test Mode."""

    def __init__(self, adapter: RazorpayAdapter | None = None) -> None:
        self.adapter = adapter or RazorpayAdapter()

    def execute_authorized_action(
        self,
        payment_id: str,
        action: str,
        decision_id: str,
        idempotency_key: str,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Execute a policy-authorized recovery action with duplicate execution protection.

        Does not allow external API errors to corrupt internal application state.
        """
        norm_action = action.upper().strip()
        action_id = f"act_{uuid.uuid4().hex[:12]}"
        now = datetime.now(UTC)
        payload = payload or {}

        payment = PaymentRepository.get_by_id(payment_id)
        if not payment:
            raise ValueError(f"Cannot execute action: payment '{payment_id}' not found.")

        # Guard: Check duplicate execution in database
        existing_action = ActionRepository.get_by_idempotency_key(idempotency_key)
        if existing_action:
            logger.warning(f"Duplicate execution blocked for idempotency key: {idempotency_key}")
            return {
                "actionId": existing_action["action_id"],
                "status": "DUPLICATE",
                "message": "Action was already executed.",
            }

        external_ref: str | None = None
        result_payload: dict[str, Any] = {}
        execution_status = "EXECUTED"
        new_recovery_status = "pending"

        try:
            if norm_action == "PAYMENT_LINK":
                amount_paise = int(payment.get("amount", 0))
                resp = self.adapter.create_payment_link(
                    amount_paise=amount_paise,
                    currency=str(payment.get("currency", "INR")),
                    customer_email=payment.get("customer_email"),
                    reference_id=f"ref_{payment_id}_{uuid.uuid4().hex[:6]}",
                )
                external_ref = resp.get("id") or f"plink_{uuid.uuid4().hex[:10]}"
                result_payload = {
                    "paymentLinkId": external_ref,
                    "shortUrl": resp.get("short_url"),
                    "amount": resp.get("amount", amount_paise),
                }
                new_recovery_status = "link_sent"

            elif norm_action == "RETRY":
                new_count = PaymentRepository.increment_retry_count(payment_id)
                external_ref = f"retry_{payment_id}_{new_count}"
                result_payload = {
                    "retryAttempt": new_count,
                    "initiatedAt": now.isoformat(),
                }
                new_recovery_status = "retrying"

            elif norm_action == "REMINDER":
                link_id = payload.get("paymentLinkId") or payment.get("last_recovery_action_id")
                if link_id and link_id.startswith("plink_"):
                    self.adapter.notify_payment_link(link_id, medium="sms")
                external_ref = f"remind_{payment_id}_{uuid.uuid4().hex[:6]}"
                result_payload = {
                    "reminderSent": True,
                    "medium": "sms",
                }
                new_recovery_status = "reminded"

            elif norm_action == "STOP":
                external_ref = f"stop_{payment_id}"
                result_payload = {
                    "stopped": True,
                    "reason": "Hard decline or retries exhausted per policy.",
                }
                new_recovery_status = "stopped"

            # Update payment state
            PaymentRepository.update_status(
                payment_id=payment_id,
                status=payment.get("status", "failed"),
                recovery_status=new_recovery_status,
                last_action_id=action_id,
            )

        except RazorpayError as exc:
            logger.error(f"External Razorpay call failed for action '{norm_action}': {exc}")
            execution_status = "FAILED"
            result_payload = {"error": exc.message, "code": exc.code}
            # Application payment state remains uncorrupted (status: failed)

        # Record action in recovery_actions
        action_doc = {
            "action_id": action_id,
            "decision_id": decision_id,
            "payment_id": payment_id,
            "action_type": norm_action,
            "idempotency_key": idempotency_key,
            "status": execution_status,
            "external_reference": external_ref,
            "payload": payload,
            "result": result_payload,
            "executed_at": now,
            "outcome": "PENDING" if execution_status == "EXECUTED" else "FAILED",
        }

        ActionRepository.create(action_doc)

        return {
            "actionId": action_id,
            "paymentId": payment_id,
            "decisionId": decision_id,
            "action": norm_action,
            "status": execution_status,
            "externalReference": external_ref,
            "result": result_payload,
        }
