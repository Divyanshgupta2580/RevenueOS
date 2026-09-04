"""Razorpay Webhook Event Processor with Idempotency and State Synchronization."""

import logging
from datetime import UTC, datetime
from typing import Any

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from apps.database.client import get_database
from apps.database.repositories import PaymentRepository, WebhookEventRepository
from apps.websocket.consumer import OPERATORS_GROUP

logger = logging.getLogger("revenueos.webhooks")


class WebhookEventProcessor:
    """Processes inbound Razorpay webhooks idempotently and broadcasts state updates."""

    @classmethod
    def broadcast_to_operators(cls, event_type: str, data: dict[str, Any]) -> None:
        """Publish real-time event to all connected dashboard operators."""
        channel_layer = get_channel_layer()
        if not channel_layer:
            return

        import asyncio

        event_msg = {
            "type": "broadcast_event",
            "event_type": event_type,
            "data": data,
        }

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        try:
            if loop and loop.is_running():
                loop.create_task(channel_layer.group_send(OPERATORS_GROUP, event_msg))
            else:
                async_to_sync(channel_layer.group_send)(OPERATORS_GROUP, event_msg)
        except Exception as exc:
            logger.warning(f"Failed to broadcast webhook event to operators group: {exc}")

    @classmethod
    def process_event(cls, payload: dict[str, Any]) -> dict[str, Any]:
        """Process inbound webhook payload idempotently."""
        event_id = payload.get("id") or payload.get("event_id")
        event_type = payload.get("event", "")

        if not event_id:
            logger.warning("Webhook rejected: missing event id.")
            return {"status": "INVALID", "reason": "Missing event id"}

        # 1. Idempotency Check
        if WebhookEventRepository.is_processed(str(event_id)):
            logger.info(f"Duplicate webhook ignored (event_id={event_id}).")
            return {"status": "ALREADY_PROCESSED", "eventId": event_id}

        # 2. Persist event document immediately
        now = datetime.now(UTC)
        event_doc = {
            "event_id": str(event_id),
            "event_type": event_type,
            "payload": payload,
            "created_at": now,
        }
        WebhookEventRepository.create(event_doc)

        # 3. Extract entities
        payload_data = payload.get("payload", {})
        payment_entity = payload_data.get("payment", {}).get("entity", {})
        plink_entity = payload_data.get("payment_link", {}).get("entity", {})

        payment_id = payment_entity.get("id")
        plink_id = plink_entity.get("id")

        db = get_database()

        # Handle Payment Captured / Paid (Recovery Success)
        if event_type in ["payment.captured", "order.paid", "payment_link.paid"]:
            # If payment link paid, match payment either by payment_id or payment link reference
            target_pid = payment_id
            if not target_pid and plink_id:
                # Find payment linked to this payment link
                linked = db.payments.find_one({"last_recovery_action_id": {"$exists": True}})
                if linked:
                    target_pid = linked.get("payment_id")

            if target_pid:
                amount_captured = payment_entity.get("amount") or plink_entity.get("amount")

                # Update payment state in MongoDB
                PaymentRepository.update_status(
                    payment_id=target_pid,
                    status="captured",
                    recovery_status="recovered",
                )

                # Update recovery_actions outcome
                db.recovery_actions.update_many(
                    {"payment_id": target_pid},
                    {"$set": {"outcome": "RECOVERED", "recovered_at": now}},
                )

                logger.info(f"Payment '{target_pid}' successfully recovered via webhook ({event_type}).")

                # Broadcast live updates to operators
                cls.broadcast_to_operators(
                    "payment.updated",
                    {
                        "paymentId": target_pid,
                        "status": "captured",
                        "recoveryStatus": "recovered",
                        "amount": amount_captured,
                        "recoveredAt": now.isoformat(),
                    },
                )
                cls.broadcast_to_operators("revenue.updated", {"paymentId": target_pid})

        # Handle Payment Failed
        elif event_type == "payment.failed":
            if payment_id:
                error_code = str(payment_entity.get("error_code") or "BAD_REQUEST_ERROR")
                error_desc = str(payment_entity.get("error_description") or "Payment failed")
                error_reason = str(payment_entity.get("error_reason") or "payment_failed")
                comb = f"{error_code} {error_desc} {error_reason}".lower()
                if "insufficient" in comb:
                    category = "insufficient_funds"
                elif "timeout" in comb or "network" in comb:
                    category = "network_timeout"
                elif "fraud" in comb or "risk" in comb or "stolen" in comb:
                    category = "fraud"
                elif "expired" in comb:
                    category = "card_expired"
                elif "auth" in comb or "otp" in comb:
                    category = "authentication_failed"
                else:
                    category = "soft_decline"

                payment = PaymentRepository.get_by_id(payment_id)
                if payment:
                    PaymentRepository.update_status(
                        payment_id=payment_id,
                        status="failed",
                        recovery_status="at_risk",
                    )
                else:
                    raw_amt = payment_entity.get("amount") or 150000
                    try:
                        amount_paise = int(raw_amt)
                    except (TypeError, ValueError):
                        amount_paise = 150000
                    currency = str(payment_entity.get("currency") or "INR")
                    order_id = str(payment_entity.get("order_id") or "")
                    email = str(payment_entity.get("email") or "operator@revenueos.local")
                    PaymentRepository.create(
                        {
                            "payment_id": payment_id,
                            "order_id": order_id,
                            "customer_id": f"cust_{payment_id[-8:]}",
                            "customer_email": email,
                            "amount": amount_paise,
                            "currency": currency,
                            "status": "failed",
                            "error_code": error_code,
                            "error_description": error_desc,
                            "failure_reason": error_reason,
                            "failure_category": category,
                            "method": str(payment_entity.get("method") or "card"),
                            "retry_count": 0,
                            "max_retries_allowed": 3,
                            "recovery_status": "at_risk",
                            "created_at": now,
                        }
                    )

                cls.broadcast_to_operators(
                    "payment.updated",
                    {
                        "paymentId": payment_id,
                        "status": "failed",
                        "recoveryStatus": "at_risk",
                        "errorCode": error_code,
                        "errorDescription": error_desc,
                        "failureCategory": category,
                    },
                )
                cls.broadcast_to_operators("revenue.updated", {"paymentId": payment_id})

        # Handle Payment Link Expired or Cancelled
        elif event_type in ["payment_link.expired", "payment_link.cancelled"]:
            if plink_id:
                status_val = "expired" if "expired" in event_type else "cancelled"
                db.recovery_actions.update_many(
                    {"external_reference": plink_id},
                    {"$set": {"outcome": status_val.upper()}},
                )
                cls.broadcast_to_operators(
                    "payment_link.updated",
                    {"paymentLinkId": plink_id, "status": status_val},
                )

        return {"status": "PROCESSED", "eventId": event_id, "type": event_type}


# Backward-compatible and descriptive alias
RazorpayWebhookProcessor = WebhookEventProcessor

