"""RevenueOS Channels WebSocket consumer skeleton for Phase 1."""

import json
from typing import Any

from channels.generic.websocket import AsyncWebsocketConsumer


class RevenueOSConsumer(AsyncWebsocketConsumer):
    """WebSocket consumer for real-time RevenueOS RPC and broadcasts."""

    async def connect(self) -> None:
        """Handle incoming WebSocket connection."""
        await self.accept()

    async def disconnect(self, close_code: int) -> None:
        """Handle client disconnect and cleanup."""
        pass

    async def receive(self, text_data: str | None = None, bytes_data: bytes | None = None) -> None:
        """Process incoming client frames."""
        if not text_data:
            return

        try:
            message: dict[str, Any] = json.loads(text_data)
            request_id = message.get("requestId", "")
            msg_type = message.get("type", "")

            if msg_type == "ping":
                await self.send(
                    text_data=json.dumps(
                        {
                            "protocolVersion": "v1",
                            "requestId": request_id,
                            "type": "pong",
                            "timestamp": "2026-09-03T18:00:00.000Z",
                            "payload": {},
                        }
                    )
                )
        except Exception:
            await self.send(
                text_data=json.dumps(
                    {
                        "protocolVersion": "v1",
                        "type": "error",
                        "error": {
                            "code": "INVALID_JSON",
                            "message": "Malformed JSON payload.",
                        },
                    }
                )
            )
