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
            "signature": payment.get("signature"),
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
        signature: str | None = None,
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
        if signature is not None:
            updates["signature"] = signature

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

    @classmethod
    def get_customer_history(cls, customer_id: str, limit: int = 10) -> dict[str, Any]:
        """Retrieve sanitized customer transaction aggregates.

        Excludes all PII, tokens, card credentials, and sensitive data.
        """
        if not customer_id or customer_id in ["unknown", ""]:
            return {
                "customer_id": "unknown",
                "total_successful_payments": 0,
                "total_failed_payments": 0,
                "recent_successful_payments_count": 0,
                "recent_failed_payments_count": 0,
                "historical_recovery_success_rate": 0.0,
                "time_since_last_success_hours": None,
            }
        col = cls.get_collection()
        cursor = (
            col.find(
                {"customer_id": customer_id},
                {"_id": 0, "status": 1, "created_at": 1, "amount": 1},
            )
            .sort("created_at", -1)
            .limit(limit)
        )
        records = list(cursor)
        successes = [r for r in records if r.get("status") in ["captured", "success"]]
        failures = [r for r in records if r.get("status") == "failed"]
        last_success = successes[0]["created_at"] if successes and "created_at" in successes[0] else None

        hours_since_success = None
        if isinstance(last_success, datetime):
            if last_success.tzinfo is None:
                last_success = last_success.replace(tzinfo=UTC)
            hours_since_success = round(max(0.0, (datetime.now(UTC) - last_success).total_seconds() / 3600.0), 1)

        total_tx = len(records)
        success_rate = round(len(successes) / total_tx, 4) if total_tx > 0 else 0.0
        return {
            "customer_id": customer_id,
            "total_successful_payments": len(successes),
            "total_failed_payments": len(failures),
            "recent_successful_payments_count": len(successes),
            "recent_failed_payments_count": len(failures),
            "historical_recovery_success_rate": success_rate,
            "time_since_last_success_hours": hours_since_success,
        }


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

        from apps.brain.config import get_configured_gemini_model

        default_model = get_configured_gemini_model()
        now = datetime.now(UTC)
        created_at = decision.get("created_at") or now
        if isinstance(created_at, str):
            try:
                created_at = datetime.fromisoformat(created_at)
            except Exception:
                created_at = now

        doc = {
            "decision_id": decision_id,
            "payment_id": payment_id,
            "model_version": decision.get("model_version", default_model),
            "endpoint": decision.get("endpoint", "recovery.analyze"),
            "request_id": decision.get("request_id") or f"req_{decision_id}",
            "payment_snapshot": decision.get("payment_snapshot", {}),
            "evidence_summary": decision.get("evidence_summary", {}),
            "ai_recommendation": decision.get("ai_recommendation", {}),
            "policy_decision": decision.get("policy_decision", {}),
            "execution_status": decision.get("execution_status", "PENDING"),
            "execution_result": decision.get("execution_result"),
            "execution_latency_ms": decision.get("execution_latency_ms"),
            "executed_at": decision.get("executed_at"),
            "outcome": decision.get("outcome", "PENDING"),
            "outcome_actual_paise": decision.get("outcome_actual_paise"),
            "outcome_at": decision.get("outcome_at"),
            "audit_timeline": decision.get("audit_timeline", []),
            "created_at": created_at,
            "updated_at": now,
        }

        col = cls.get_collection()
        col.insert_one(doc)
        return doc

    @classmethod
    def update_execution(
        cls,
        decision_id: str,
        execution_status: str,
        execution_result: dict[str, Any] | None = None,
        execution_latency_ms: float | None = None,
        executed_at: datetime | None = None,
        outcome: str = "PENDING",
        actual_recovery_paise: int | None = None,
    ) -> bool:
        """Update decision record with execution details and append to audit timeline."""
        col = cls.get_collection()
        now = executed_at or datetime.now(UTC)
        updates: dict[str, Any] = {
            "execution_status": execution_status,
            "execution_result": execution_result or {},
            "executed_at": now,
            "outcome": outcome,
            "updated_at": now,
        }
        if execution_latency_ms is not None:
            updates["execution_latency_ms"] = execution_latency_ms
        if actual_recovery_paise is not None:
            updates["outcome_actual_paise"] = actual_recovery_paise

        timeline_entry = {
            "stage": "EXECUTION",
            "title": f"Recovery Action {execution_status}",
            "status": execution_status,
            "timestamp": now.isoformat(),
            "details": execution_result or {},
        }
        res = col.update_one(
            {"decision_id": decision_id},
            {
                "$set": updates,
                "$push": {"audit_timeline": timeline_entry},
            },
        )
        return bool(res.modified_count > 0)

    @classmethod
    def _format_decision_doc(cls, doc: dict[str, Any]) -> dict[str, Any]:
        """Format decision document with standard ISO dates and camelCase aliases for the frontend."""
        item = dict(doc)
        for date_key in ["created_at", "updated_at", "executed_at", "outcome_at"]:
            val = item.get(date_key)
            if isinstance(val, datetime):
                item[date_key] = val.isoformat()

        # Format ai_recommendation
        ai_rec = dict(item.get("ai_recommendation") or {})
        if "expected_recovery_value_paise" in ai_rec and "expectedRecoveryValuePaise" not in ai_rec:
            ai_rec["expectedRecoveryValuePaise"] = ai_rec["expected_recovery_value_paise"]
        if "supporting_factors" in ai_rec and "supportingFactors" not in ai_rec:
            ai_rec["supportingFactors"] = ai_rec["supporting_factors"]
        if "risk_factors" in ai_rec and "riskFactors" not in ai_rec:
            ai_rec["riskFactors"] = ai_rec["risk_factors"]
        item["ai_recommendation"] = ai_rec

        # Format policy_decision
        policy_dec = dict(item.get("policy_decision") or {})
        if "rules_evaluated" in policy_dec and "rulesEvaluated" not in policy_dec:
            policy_dec["rulesEvaluated"] = policy_dec["rules_evaluated"]
        if "blocking_rule" in policy_dec and "blockingRule" not in policy_dec:
            policy_dec["blockingRule"] = policy_dec["blocking_rule"]
        if "blocking_reason" in policy_dec and "blockingReason" not in policy_dec:
            policy_dec["blockingReason"] = policy_dec["blocking_reason"]
        if "authorized_action" in policy_dec and "authorizedAction" not in policy_dec:
            policy_dec["authorizedAction"] = policy_dec["authorized_action"]
        item["policy_decision"] = policy_dec

        # CamelCase top-level aliases
        item["decisionId"] = item.get("decision_id")
        item["paymentId"] = item.get("payment_id")
        item["modelVersion"] = item.get("model_version")
        item["requestId"] = item.get("request_id")
        item["paymentSnapshot"] = item.get("payment_snapshot", {})
        item["evidenceSummary"] = item.get("evidence_summary", {})
        item["aiRecommendation"] = ai_rec
        item["policyDecision"] = policy_dec
        item["executionStatus"] = item.get("execution_status", "PENDING")
        item["executionResult"] = item.get("execution_result")
        item["executionLatencyMs"] = item.get("execution_latency_ms")
        item["executedAt"] = item.get("executed_at")
        item["outcomeActualPaise"] = item.get("outcome_actual_paise")
        item["outcomeAt"] = item.get("outcome_at")
        item["auditTimeline"] = item.get("audit_timeline", [])
        item["createdAt"] = item.get("created_at")
        item["updatedAt"] = item.get("updated_at")

        return item

    @classmethod
    def get_by_id(cls, decision_id: str) -> dict[str, Any] | None:
        """Retrieve a single decision record by ID with formatted timestamps."""
        col = cls.get_collection()
        doc = col.find_one({"decision_id": decision_id}, {"_id": 0})
        if not doc:
            return None
        return cls._format_decision_doc(doc)

    @classmethod
    def list_decisions(
        cls,
        page: int = 1,
        page_size: int = 50,
        payment_id: str | None = None,
        action: str | None = None,
        policy_status: str | None = None,
        execution_status: str | None = None,
        search: str | None = None,
    ) -> tuple[list[dict[str, Any]], int]:
        """Audit ledger listing with bounded pagination and robust filtering."""
        bounded_size = min(max(1, page_size), 100)
        skip = (max(1, page) - 1) * bounded_size

        query: dict[str, Any] = {}
        if payment_id:
            query["payment_id"] = payment_id
        if action and action.upper() != "ALL":
            query["ai_recommendation.action"] = action.upper()
        if policy_status and policy_status.upper() != "ALL":
            query["policy_decision.status"] = policy_status.upper()
        if execution_status and execution_status.upper() != "ALL":
            query["execution_status"] = execution_status.upper()
        if search:
            s = str(search).strip()
            query["$or"] = [
                {"decision_id": {"$regex": s, "$options": "i"}},
                {"payment_id": {"$regex": s, "$options": "i"}},
            ]

        col = cls.get_collection()
        cursor = (
            col.find(query, {"_id": 0})
            .sort("created_at", -1)
            .skip(skip)
            .limit(bounded_size)
        )
        total = col.count_documents(query) if hasattr(col, "count_documents") else len(list(col.find(query)))
        records = [cls._format_decision_doc(d) for d in cursor]
        return records, total



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

    @classmethod
    def get_payment_action_history(cls, payment_id: str, limit: int = 5) -> list[dict[str, Any]]:
        """Retrieve recent recovery actions executed for a specific payment."""
        if not payment_id:
            return []
        col = cls.get_collection()
        cursor = (
            col.find(
                {"payment_id": payment_id},
                {
                    "_id": 0,
                    "action_type": 1,
                    "status": 1,
                    "outcome": 1,
                    "executed_at": 1,
                    "external_reference": 1,
                },
            )
            .sort("executed_at", -1)
            .limit(limit)
        )
        return [dict(d) for d in cursor]


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
