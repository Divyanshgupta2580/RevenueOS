"""PyMongo repositories for RevenueOS data models.

Provides bounded reads, projections, pagination, and integer minor currency validation.
Follows the absolute no-dummy data rule.
"""

from datetime import UTC, datetime
from typing import Any

from apps.core.exceptions import RevenueOSError
from apps.core.money import validate_minor_units
from apps.database.client import get_database


class DatabaseError(RevenueOSError):
    """Raised when a database validation or constraint violation occurs."""
    def __init__(self, message: str) -> None:
        super().__init__(message, code="DATABASE_ERROR")


class PaymentRepository:
    """Repository for payments collection."""

    @staticmethod
    def get_collection() -> Any:
        return get_database()["payments"]

    @classmethod
    def create(cls, payment: dict[str, Any]) -> dict[str, Any]:
        """Insert a new payment document enforcing integer minor units."""
        payment_id = payment.get("payment_id")
        if not payment_id:
            raise DatabaseError("payment_id is required.")

        amount = payment.get("amount")
        if not isinstance(amount, int):
            raise DatabaseError(f"Monetary amount must be an integer minor unit (paise), got {type(amount).__name__}")

        try:
            validated_amount = validate_minor_units(amount)
        except Exception as exc:
            raise DatabaseError(f"Invalid monetary amount: {exc}") from exc

        col = cls.get_collection()
        existing = col.find_one({"payment_id": payment_id})
        if existing:
            raise DatabaseError(f"Payment with ID '{payment_id}' already exists.")

        now = datetime.now(UTC)
        doc = {
            "payment_id": payment_id,
            "order_id": payment.get("order_id"),
            "customer_id": payment.get("customer_id"),
            "customer_email": payment.get("customer_email"),
            "amount": validated_amount,  # Integer paise
            "currency": payment.get("currency", "INR"),
            "status": payment.get("status", "failed"),
            "error_code": payment.get("error_code"),
            "error_description": payment.get("error_description"),
            "failure_reason": payment.get("failure_reason", "unknown"),
            "failure_category": payment.get("failure_category", "soft_decline"),
            "retry_count": int(payment.get("retry_count", 0)),
            "max_retries_allowed": int(payment.get("max_retries_allowed", 3)),
            "recovery_status": payment.get("recovery_status", "pending"),
            "last_recovery_action_id": None,
            "created_at": payment.get("created_at", now),
            "updated_at": now,
        }

        col.insert_one(doc)
        return doc

    @classmethod
    def get_by_id(cls, payment_id: str) -> dict[str, Any] | None:
        """Retrieve single payment by ID with bounded projection."""
        col = cls.get_collection()
        doc = col.find_one({"payment_id": payment_id}, {"_id": 0})
        return dict(doc) if doc else None

    @classmethod
    def update_status(
        cls,
        payment_id: str,
        status: str,
        recovery_status: str | None = None,
        last_action_id: str | None = None,
    ) -> bool:
        """Update payment and recovery status."""
        col = cls.get_collection()
        updates: dict[str, Any] = {
            "status": status,
            "updated_at": datetime.now(UTC),
        }
        if recovery_status is not None:
            updates["recovery_status"] = recovery_status
        if last_action_id is not None:
            updates["last_recovery_action_id"] = last_action_id

        res = col.update_one({"payment_id": payment_id}, {"$set": updates})
        return bool(res.modified_count > 0)

    @classmethod
    def increment_retry_count(cls, payment_id: str) -> int:
        """Increment retry count deterministically."""
        col = cls.get_collection()
        doc = col.find_one_and_update(
            {"payment_id": payment_id},
            {"$inc": {"retry_count": 1}, "$set": {"updated_at": datetime.now(UTC)}},
            projection={"_id": 0, "retry_count": 1},
            return_document=True,
        )
        return int(doc["retry_count"]) if doc else 0

    @classmethod
    def list_opportunities(
        cls,
        status: str = "failed",
        recovery_status: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        """Bounded, paginated list of revenue opportunities."""
        bounded_size = min(max(1, page_size), 100)
        skip = (max(1, page) - 1) * bounded_size

        query: dict[str, Any] = {"status": status}
        if recovery_status:
            query["recovery_status"] = recovery_status

        col = cls.get_collection()
        cursor = (
            col.find(query, {"_id": 0})
            .sort("updated_at", -1)
            .skip(skip)
            .limit(bounded_size)
        )
        total = col.count_documents(query) if hasattr(col, "count_documents") else len(list(col.find(query)))
        return [dict(d) for d in cursor], total


class DecisionRepository:
    """Repository for recovery_decisions collection."""

    @staticmethod
    def get_collection() -> Any:
        return get_database()["recovery_decisions"]

    @classmethod
    def create(cls, decision: dict[str, Any]) -> dict[str, Any]:
        """Persist structured AI recommendation and deterministic policy result."""
        decision_id = decision.get("decision_id")
        payment_id = decision.get("payment_id")
        if not decision_id or not payment_id:
            raise DatabaseError("decision_id and payment_id are required.")

        now = datetime.now(UTC)
        doc = {
            "decision_id": decision_id,
            "payment_id": payment_id,
            "model_version": decision.get("model_version", "gemini-2.5-flash"),
            "ai_recommendation": decision.get("ai_recommendation", {}),
            "policy_decision": decision.get("policy_decision", {}),
            "created_at": decision.get("created_at", now),
        }

        col = cls.get_collection()
        col.insert_one(doc)
        return doc

    @classmethod
    def get_by_id(cls, decision_id: str) -> dict[str, Any] | None:
        col = cls.get_collection()
        doc = col.find_one({"decision_id": decision_id}, {"_id": 0})
        return dict(doc) if doc else None

    @classmethod
    def list_decisions(cls, page: int = 1, page_size: int = 50) -> tuple[list[dict[str, Any]], int]:
        """Audit ledger listing with bounded pagination."""
        bounded_size = min(max(1, page_size), 100)
        skip = (max(1, page) - 1) * bounded_size

        col = cls.get_collection()
        cursor = (
            col.find({}, {"_id": 0})
            .sort("created_at", -1)
            .skip(skip)
            .limit(bounded_size)
        )
        total = col.count_documents({}) if hasattr(col, "count_documents") else len(list(col.find({})))
        return [dict(d) for d in cursor], total


class ActionRepository:
    """Repository for recovery_actions collection."""

    @staticmethod
    def get_collection() -> Any:
        return get_database()["recovery_actions"]

    @classmethod
    def create(cls, action: dict[str, Any]) -> dict[str, Any]:
        """Record recovery action execution with idempotency guard."""
        action_id = action.get("action_id")
        idempotency_key = action.get("idempotency_key")
        payment_id = action.get("payment_id")

        if not action_id or not idempotency_key or not payment_id:
            raise DatabaseError("action_id, idempotency_key, and payment_id are required.")

        col = cls.get_collection()
        existing = col.find_one({"idempotency_key": idempotency_key})
        if existing:
            raise DatabaseError(f"Action with idempotency key '{idempotency_key}' already exists.")

        now = datetime.now(UTC)
        doc = {
            "action_id": action_id,
            "decision_id": action.get("decision_id"),
            "payment_id": payment_id,
            "action_type": action.get("action_type"),
            "idempotency_key": idempotency_key,
            "status": action.get("status", "EXECUTED"),
            "external_reference": action.get("external_reference"),
            "payload": action.get("payload", {}),
            "result": action.get("result", {}),
            "executed_at": action.get("executed_at", now),
            "outcome": action.get("outcome", "PENDING"),
        }

        col.insert_one(doc)
        return doc

    @classmethod
    def get_by_idempotency_key(cls, key: str) -> dict[str, Any] | None:
        col = cls.get_collection()
        doc = col.find_one({"idempotency_key": key}, {"_id": 0})
        return dict(doc) if doc else None

    @classmethod
    def get_by_id(cls, action_id: str) -> dict[str, Any] | None:
        col = cls.get_collection()
        doc = col.find_one({"action_id": action_id}, {"_id": 0})
        return dict(doc) if doc else None

    @classmethod
    def update_outcome(
        cls,
        action_id: str,
        status: str,
        outcome: str,
        result_updates: dict[str, Any] | None = None,
    ) -> bool:
        col = cls.get_collection()
        updates: dict[str, Any] = {
            "status": status,
            "outcome": outcome,
            "updated_at": datetime.now(UTC),
        }
        if result_updates:
            updates["result"] = result_updates

        res = col.update_one({"action_id": action_id}, {"$set": updates})
        return bool(res.modified_count > 0)


class WebhookEventRepository:
    """Repository for webhook_events collection with strict idempotency."""

    @staticmethod
    def get_collection() -> Any:
        return get_database()["webhook_events"]

    @classmethod
    def is_processed(cls, event_id: str) -> bool:
        """Check if a webhook event has already been received and processed."""
        col = cls.get_collection()
        doc = col.find_one({"event_id": event_id})
        return doc is not None

    @classmethod
    def record_event(cls, event: dict[str, Any]) -> dict[str, Any]:
        """Record verified webhook event payload."""
        event_id = event.get("event_id")
        if not event_id:
            raise DatabaseError("event_id is required.")

        col = cls.get_collection()
        if cls.is_processed(event_id):
            raise DatabaseError(f"Webhook event '{event_id}' was already recorded.")

        now = datetime.now(UTC)
        doc = {
            "event_id": event_id,
            "event_type": event.get("event_type"),
            "payment_id": event.get("payment_id"),
            "signature_valid": bool(event.get("signature_valid", True)),
            "processed": True,
            "received_at": event.get("received_at", now),
            "payload_summary": event.get("payload_summary", {}),
        }

        col.insert_one(doc)
        return doc

    create = record_event
