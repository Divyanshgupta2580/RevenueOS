"""Acceptance tests for Phase 3: WebSocket System & Protocol v1."""

import json
from collections.abc import Sequence
from typing import Any

import pytest
from asgiref.testing import ApplicationCommunicator

from apps.websocket.consumer import RevenueOSConsumer
from apps.websocket.protocol import MAX_FRAME_SIZE


class WebsocketTestCommunicator(ApplicationCommunicator):
    """ASGI-compliant WebSocket test communicator using asgiref."""

    def __init__(
        self,
        application: Any,
        path: str = "/ws/v1/app/",
        user: dict[str, Any] | None = None,
        headers: Sequence[tuple[bytes, bytes]] | None = None,
    ) -> None:
        scope = {
            "type": "websocket",
            "path": path,
            "headers": list(headers or []),
            "user": user,
        }
        super().__init__(application, scope)

    async def connect(self, timeout: float = 2.0) -> tuple[bool, int | None]:
        await self.send_input({"type": "websocket.connect"})
        response = await self.receive_output(timeout=timeout)
        if response["type"] == "websocket.accept":
            return True, None
        if response["type"] == "websocket.close":
            return False, response.get("code")
        return False, None

    async def send_to(self, text_data: str) -> None:
        await self.send_input({"type": "websocket.receive", "text": text_data})

    async def receive_from(self, timeout: float = 2.0) -> str:
        response = await self.receive_output(timeout=timeout)
        assert response["type"] == "websocket.send"
        return str(response.get("text", ""))

    async def disconnect(self, code: int = 1000) -> None:
        await self.send_input({"type": "websocket.disconnect", "code": code})


@pytest.mark.asyncio
async def test_websocket_unauthenticated_rejected() -> None:
    """Acceptance Test: Unauthenticated connection is rejected with 4401."""
    communicator = WebsocketTestCommunicator(RevenueOSConsumer.as_asgi(), user=None)
    connected, close_code = await communicator.connect()
    assert not connected
    assert close_code == 4401


@pytest.mark.asyncio
async def test_websocket_authenticated_connect_and_heartbeat() -> None:
    """Acceptance Test: Authenticated connection succeeds and handles ping/pong."""
    application = RevenueOSConsumer.as_asgi()
    user = {
        "id": "usr_test_123",
        "username": "operator@revenueos.internal",
        "role": "operator",
    }
    communicator = WebsocketTestCommunicator(application, user=user)

    connected, _ = await communicator.connect()
    assert connected

    # Send heartbeat ping
    ping_frame = {
        "protocolVersion": "v1",
        "requestId": "req_ping_001",
        "type": "ping",
        "timestamp": "2026-09-03T18:00:00.000Z",
        "payload": {},
    }
    await communicator.send_to(text_data=json.dumps(ping_frame))

    response_text = await communicator.receive_from()
    response = json.loads(response_text)

    assert response["protocolVersion"] == "v1"
    assert response["requestId"] == "req_ping_001"
    assert response["type"] == "pong"
    assert "serverTime" in response["payload"]

    await communicator.disconnect()


@pytest.mark.asyncio
async def test_websocket_malformed_json_rejected() -> None:
    """Acceptance Test: Malformed JSON is rejected with structured error."""
    user = {"id": "usr_test_123", "username": "operator"}
    communicator = WebsocketTestCommunicator(RevenueOSConsumer.as_asgi(), user=user)
    await communicator.connect()

    await communicator.send_to(text_data="INVALID_NOT_JSON{{{")
    response_text = await communicator.receive_from()
    response = json.loads(response_text)

    assert response["type"] == "error"
    assert response["error"]["code"] == "INVALID_JSON"

    await communicator.disconnect()


@pytest.mark.asyncio
async def test_websocket_unsupported_version_rejected() -> None:
    """Acceptance Test: Unsupported protocol version is rejected."""
    user = {"id": "usr_test_123", "username": "operator"}
    communicator = WebsocketTestCommunicator(RevenueOSConsumer.as_asgi(), user=user)
    await communicator.connect()

    invalid_version_frame = {
        "protocolVersion": "v99",
        "requestId": "req_ver_001",
        "type": "ping",
        "payload": {},
    }
    await communicator.send_to(text_data=json.dumps(invalid_version_frame))
    response = json.loads(await communicator.receive_from())

    assert response["type"] == "error"
    assert response["error"]["code"] == "UNSUPPORTED_VERSION"

    await communicator.disconnect()


@pytest.mark.asyncio
async def test_websocket_payload_too_large_rejected() -> None:
    """Acceptance Test: Payloads exceeding 32 KB are rejected."""
    user = {"id": "usr_test_123", "username": "operator"}
    communicator = WebsocketTestCommunicator(RevenueOSConsumer.as_asgi(), user=user)
    await communicator.connect()

    huge_payload = "X" * (MAX_FRAME_SIZE + 100)
    huge_frame = {
        "protocolVersion": "v1",
        "requestId": "req_huge_001",
        "type": "ping",
        "payload": {"data": huge_payload},
    }
    await communicator.send_to(text_data=json.dumps(huge_frame))
    response = json.loads(await communicator.receive_from())

    assert response["type"] == "error"
    assert response["error"]["code"] == "PAYLOAD_TOO_LARGE"

    await communicator.disconnect()


@pytest.mark.asyncio
async def test_websocket_duplicate_execution_blocked() -> None:
    """Acceptance Test: Duplicate recovery actions in the same session are blocked."""
    user = {"id": "usr_test_123", "username": "operator"}
    communicator = WebsocketTestCommunicator(RevenueOSConsumer.as_asgi(), user=user)
    await communicator.connect()

    execute_frame = {
        "protocolVersion": "v1",
        "requestId": "req_exec_001",
        "type": "recovery.execute",
        "timestamp": "2026-09-03T18:00:00.000Z",
        "payload": {
            "paymentId": "pay_test_dup_001",
            "action": "PAYMENT_LINK",
            "idempotencyKey": "idemp_pay_test_dup_001_1",
        },
    }

    # First attempt succeeds / queues
    await communicator.send_to(text_data=json.dumps(execute_frame))
    res1 = json.loads(await communicator.receive_from())
    assert res1["type"] == "recovery.executed"
    assert res1["payload"]["status"] == "QUEUED"

    # Second immediate duplicate attempt with same idempotency key is blocked
    execute_frame["requestId"] = "req_exec_002"
    await communicator.send_to(text_data=json.dumps(execute_frame))
    res2 = json.loads(await communicator.receive_from())
    assert res2["type"] == "error"
    assert res2["error"]["code"] == "DUPLICATE_EXECUTION"

    await communicator.disconnect()


@pytest.mark.asyncio
async def test_websocket_rate_limiting() -> None:
    """Acceptance Test: Bursting beyond rate limit generates RATE_LIMITED error."""
    user = {"id": "usr_rate_limited_test", "username": "operator"}
    communicator = WebsocketTestCommunicator(RevenueOSConsumer.as_asgi(), user=user)
    await communicator.connect()

    sensitive_frame = {
        "protocolVersion": "v1",
        "requestId": "req_burst",
        "type": "recovery.analyze",
        "payload": {"paymentId": "pay_test_rate_001"},
    }

    rate_limited = False
    # Burst 15 calls (sensitive capacity is 10)
    for i in range(15):
        sensitive_frame["requestId"] = f"req_burst_{i}"
        await communicator.send_to(text_data=json.dumps(sensitive_frame))
        res = json.loads(await communicator.receive_from())
        if res.get("type") == "error" and res.get("error", {}).get("code") == "RATE_LIMITED":
            rate_limited = True
            break

    assert rate_limited is True
    await communicator.disconnect()
