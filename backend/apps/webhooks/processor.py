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
                error_code = payment_entity.get("error_code", "unknown")
                error_desc = payment_entity.get("error_description", "")
                PaymentRepository.update_status(
                    payment_id=payment_id,
                    status="failed",
                    recovery_status="pending",
                )
                cls.broadcast_to_operators(
                    "payment.updated",
                    {
                        "paymentId": payment_id,
                        "status": "failed",
                        "errorCode": error_code,
                        "errorDescription": error_desc,
                    },
                )

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
