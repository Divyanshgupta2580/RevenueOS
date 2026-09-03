"""RevenueOS authenticated Channels consumer.

Handles bidirectional RPC commands, group broadcasts, heartbeat, rate limiting,
and duplicate protection.
"""

import json
import logging
from datetime import UTC, datetime
from typing import Any

from channels.generic.websocket import AsyncWebsocketConsumer
from django.conf import settings

from apps.websocket.protocol import (
    MAX_FRAME_SIZE,
    ProtocolValidationError,
    build_error,
    build_response,
    validate_client_frame,
)
from apps.websocket.rate_limiter import rate_limiter

logger = logging.getLogger("revenueos.websocket")
OPERATORS_GROUP = "revenueos_operators"


class RevenueOSConsumer(AsyncWebsocketConsumer):
    """Authenticated real-time application consumer."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.user: dict[str, Any] | None = None
        self.user_session_id: str = ""
        self.last_activity: datetime = datetime.now(UTC)
        self._processed_executions: set[str] = set()

    async def connect(self) -> None:
        """Handshake authentication, origin check, and group join."""
        # 1. Production Origin Validation
        if not getattr(settings, "DEBUG", True):
            headers = dict(self.scope.get("headers", []))
            origin = headers.get(b"origin", b"").decode("utf-8")
            if origin:
                allowed = getattr(settings, "WS_ALLOWED_ORIGINS", [])
                if allowed and not any(origin.startswith(ao) for ao in allowed):
                    logger.warning(f"Rejected WebSocket connection from untrusted origin: {origin}")
                    await self.close(code=4403)
                    return

        self.user = self.scope.get("user")
        if not self.user:
            logger.warning("Rejected unauthenticated WebSocket connection attempt.")
            await self.close(code=4401)
            return

        self.user_session_id = str(self.user.get("id", "anonymous"))
        self.last_activity = datetime.now(UTC)

        # Join the operators broadcast group
        if self.channel_layer:
            await self.channel_layer.group_add(OPERATORS_GROUP, self.channel_name)

        await self.accept()
        logger.info(f"WebSocket connected for user '{self.user.get('username')}' [{self.channel_name}]")

    async def disconnect(self, close_code: int) -> None:
        """Leave operators group and release consumer state."""
        if self.channel_layer:
            await self.channel_layer.group_discard(OPERATORS_GROUP, self.channel_name)
        logger.info(f"WebSocket disconnected with code {close_code} [{self.channel_name}]")

    async def broadcast_event(self, event: dict[str, Any]) -> None:
        """Receive group broadcast from webhook or background service and forward to client."""
        event_type = str(event.get("event_type", "payment.updated"))
        data = event.get("data", {})
        await self.send(text_data=build_response(event_type, data))

    async def receive(self, text_data: str | None = None, bytes_data: bytes | None = None) -> None:
        """Validate, rate-limit, and dispatch incoming client frames."""
        self.last_activity = datetime.now(UTC)

        if not text_data:
            if bytes_data and len(bytes_data) > MAX_FRAME_SIZE:
                await self.send(
                    text_data=build_error("PAYLOAD_TOO_LARGE", "Binary frame exceeds 32 KB limit.")
                )
            return

        # 1. Envelope and Protocol Validation
        try:
            frame = validate_client_frame(text_data)
        except ProtocolValidationError as exc:
            await self.send(text_data=build_error(exc.code, exc.message))
            return

        request_id = frame.get("requestId")
        msg_type = frame.get("type", "")
        payload = frame.get("payload") or {}

        # 2. Rate Limiting Check
        is_sensitive = msg_type in ["recovery.analyze", "recovery.execute"]
        capacity = 10.0 if is_sensitive else 60.0
        rate = 0.2 if is_sensitive else 1.0

        if not rate_limiter.is_allowed(self.user_session_id, msg_type, capacity, rate):
            logger.warning(f"Rate limit exceeded for user '{self.user_session_id}' on command '{msg_type}'")
            await self.send(
                text_data=build_error(
                    "RATE_LIMITED",
                    f"Rate limit exceeded for '{msg_type}'. Please slow down.",
                    request_id=request_id,
                )
            )
            return

        # 3. Command Routing
        try:
            await self._dispatch_command(msg_type, payload, request_id)
        except Exception as exc:
            logger.exception(f"Unhandled error processing command '{msg_type}': {exc}")
            await self.send(
                text_data=build_error(
                    "INTERNAL_ERROR",
                    "An error occurred while processing your request.",
                    request_id=request_id,
                )
            )

    async def _dispatch_command(
        self,
        msg_type: str,
        payload: dict[str, Any],
        request_id: str | None,
    ) -> None:
        """Route validated command to appropriate application handler."""
        if msg_type == "ping":
            await self.send(
                text_data=build_response(
                    "pong",
                    {"serverTime": datetime.now(UTC).isoformat()},
                    request_id=request_id,
                )
            )
            return

        if msg_type == "revenue.list":
            page = int(payload.get("page", 1))
            page_size = int(payload.get("pageSize", 20))
            status_filter = str(payload.get("status", "failed"))

            from asgiref.sync import sync_to_async

            from apps.database.repositories import PaymentRepository
            from apps.radar.service import RevenueRadarService

            def fetch_and_rank() -> dict[str, Any]:
                payments, _ = PaymentRepository.list_opportunities(
                    status=status_filter, page=page, page_size=page_size
                )
                return RevenueRadarService.rank_opportunities(
                    payments, page=page, page_size=page_size
                )

            radar_data = await sync_to_async(fetch_and_rank)()

            await self.send(
                text_data=build_response(
                    "revenue.list.response",
                    radar_data,
                    request_id=request_id,
                )
            )
            return

        if msg_type == "revenue.details":
            payment_id = payload.get("paymentId")
            if not payment_id:
                await self.send(
                    text_data=build_error("INVALID_ARGUMENT", "paymentId is required.", request_id)
                )
                return

            from asgiref.sync import sync_to_async

            from apps.database.repositories import PaymentRepository
            from apps.radar.service import RevenueRadarService

            pid = str(payment_id)

            def fetch_detail() -> dict[str, Any] | None:
                payment = PaymentRepository.get_by_id(pid)
                if not payment:
                    return None
                return RevenueRadarService.evaluate_opportunity(payment)

            opportunity = await sync_to_async(fetch_detail)()

            await self.send(
                text_data=build_response(
                    "revenue.details.response",
                    {"opportunity": opportunity},
                    request_id=request_id,
                )
            )
            return

        if msg_type == "recovery.analyze":
            payment_id = payload.get("paymentId")
            if not payment_id:
                await self.send(
                    text_data=build_error("INVALID_ARGUMENT", "paymentId is required.", request_id)
                )
                return

            pid = str(payment_id)
            await self.send(
                text_data=build_response(
                    "analysis.started",
                    {"paymentId": pid},
                    request_id=request_id,
                )
            )

            from asgiref.sync import sync_to_async

            from apps.brain.service import RecoveryBrainService
            from apps.database.repositories import PaymentRepository

            payment = await sync_to_async(PaymentRepository.get_by_id)(pid)
            if not payment:
                await self.send(
                    text_data=build_error(
                        "NOT_FOUND",
                        f"Payment with ID '{pid}' was not found.",
                        request_id=request_id,
                    )
                )
                return

            brain_svc = RecoveryBrainService()
            recommendation = await brain_svc.analyze_payment_async(payment)
            result = (
                recommendation.model_dump()
                if hasattr(recommendation, "model_dump")
                else dict(recommendation)
            )

            await self.send(
                text_data=build_response(
                    "analysis.completed",
                    {"paymentId": pid, "recommendation": result},
                    request_id=request_id,
                )
            )
            return

        if msg_type == "recovery.execute":
            payment_id = payload.get("paymentId")
            action = payload.get("action")
            if not payment_id or not action:
                await self.send(
                    text_data=build_error("INVALID_ARGUMENT", "paymentId and action are required.", request_id)
                )
                return

            pid = str(payment_id)
            act = str(action)
            idempotency_key = str(payload.get("idempotencyKey") or f"{pid}:{act}")

            # Session-level duplicate guard
            if idempotency_key in self._processed_executions:
                await self.send(
                    text_data=build_error(
                        "DUPLICATE_EXECUTION",
                        "This recovery action has already been dispatched in this session.",
                        request_id=request_id,
                    )
                )
                return

            from asgiref.sync import sync_to_async

            from apps.policy.service import GuardedAutopilotService

            def evaluate_policy() -> tuple[dict[str, Any], str]:
                verdict, dec_id = GuardedAutopilotService.evaluate_and_record(
                    payment_id=pid,
                    action=act,
                    user=self.user,
                    idempotency_key=idempotency_key,
                    ai_recommendation=payload.get("aiRecommendation"),
                )
                return verdict.to_dict(), dec_id

            verdict_dict, decision_id = await sync_to_async(evaluate_policy)()

            if verdict_dict.get("status") == "BLOCKED":
                await self.send(
                    text_data=build_response(
                        "recovery.blocked",
                        {
                            "paymentId": pid,
                            "action": act,
                            "decisionId": decision_id,
                            "blockingRule": verdict_dict.get("blockingRule"),
                            "blockingReason": verdict_dict.get("blockingReason"),
                        },
                        request_id=request_id,
                    )
                )
                return

            # Action is APPROVED by deterministic policy engine
            self._processed_executions.add(idempotency_key)

            await self.send(
                text_data=build_response(
                    "recovery.approved",
                    {
                        "paymentId": pid,
                        "action": act,
                        "decisionId": decision_id,
                    },
                    request_id=request_id,
                )
            )

            from apps.razorpay_adapter.service import RazorpayRecoveryExecutor

            def run_execution() -> dict[str, Any]:
                executor = RazorpayRecoveryExecutor()
                return executor.execute_authorized_action(
                    payment_id=pid,
                    action=act,
                    decision_id=decision_id,
                    idempotency_key=idempotency_key,
                    payload=payload,
                )

            exec_outcome = await sync_to_async(run_execution)()

            await self.send(
                text_data=build_response(
                    "recovery.executed",
                    exec_outcome,
                    request_id=request_id,
                )
            )
            return

        if msg_type == "decision.explain":
            dec_arg = payload.get("decisionId")
            if not dec_arg:
                await self.send(
                    text_data=build_error("INVALID_ARGUMENT", "decisionId is required.", request_id)
                )
                return

            from asgiref.sync import sync_to_async

            from apps.database.repositories import DecisionRepository

            did = str(dec_arg)

            def get_explanation() -> dict[str, Any] | None:
                return DecisionRepository.get_by_id(did)

            decision_doc = await sync_to_async(get_explanation)()

            await self.send(
                text_data=build_response(
                    "decision.explain.response",
                    {"decisionId": did, "decision": decision_doc},
                    request_id=request_id,
                )
            )
            return

        if msg_type == "metrics.summary":
            from asgiref.sync import sync_to_async

            from apps.metrics.service import MetricsService

            def get_metrics() -> dict[str, Any]:
                return MetricsService.compute_summary()

            summary_data = await sync_to_async(get_metrics)()

            await self.send(
                text_data=build_response(
                    "metrics.summary.response",
                    summary_data,
                    request_id=request_id,
                )
            )
            return

        # Unknown command verb
        await self.send(
            text_data=build_error(
                "UNKNOWN_COMMAND",
                f"Unknown command type '{msg_type}'.",
                request_id=request_id,
            )
        )

    async def broadcast_message(self, event: dict[str, Any]) -> None:
        """Handler for Channel Layer group broadcasts."""
        message = event.get("message", {})
        if isinstance(message, dict):
            await self.send(text_data=json.dumps(message))
        elif isinstance(message, str):
            await self.send(text_data=message)
