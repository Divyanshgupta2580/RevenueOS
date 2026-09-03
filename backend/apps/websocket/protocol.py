"""RevenueOS WebSocket Protocol v1 frame validation and serialization."""

import json
from datetime import UTC, datetime
from typing import Any

PROTOCOL_VERSION = "v1"
MAX_FRAME_SIZE = 32768  # 32 KB bound


class ProtocolValidationError(Exception):
    """Raised when an incoming client frame violates the protocol standard."""
    def __init__(self, message: str, code: str = "MALFORMED_FRAME") -> None:
        super().__init__(message)
        self.message = message
        self.code = code


def validate_client_frame(text_data: str) -> dict[str, Any]:
    """Validate incoming client frame size, JSON syntax, and envelope structure."""
    if len(text_data.encode("utf-8")) > MAX_FRAME_SIZE:
        raise ProtocolValidationError(
            f"Frame exceeds maximum permitted size of {MAX_FRAME_SIZE} bytes.",
            code="PAYLOAD_TOO_LARGE",
        )

    try:
        data = json.loads(text_data)
    except Exception as exc:
        raise ProtocolValidationError(
            "Malformed JSON payload.",
            code="INVALID_JSON",
        ) from exc

    if not isinstance(data, dict):
        raise ProtocolValidationError(
            "Frame root must be a JSON object.",
            code="INVALID_ENVELOPE",
        )

    msg_version = data.get("protocolVersion")
    if msg_version != PROTOCOL_VERSION:
        raise ProtocolValidationError(
            f"Unsupported protocol version '{msg_version}'. Expected '{PROTOCOL_VERSION}'.",
            code="UNSUPPORTED_VERSION",
        )

    msg_type = data.get("type")
    if not isinstance(msg_type, str) or not msg_type.strip():
        raise ProtocolValidationError(
            "Message frame must include a non-empty 'type' string.",
            code="INVALID_TYPE",
        )

    # Validate payload is a dictionary if provided
    payload = data.get("payload")
    if payload is not None and not isinstance(payload, dict):
        raise ProtocolValidationError(
            "Message 'payload' must be a JSON object.",
            code="INVALID_PAYLOAD",
        )

    return data


def build_response(
    msg_type: str,
    payload: dict[str, Any],
    request_id: str | None = None,
) -> str:
    """Build compliant protocol server response frame."""
    frame: dict[str, Any] = {
        "protocolVersion": PROTOCOL_VERSION,
        "type": msg_type,
        "timestamp": datetime.now(UTC).isoformat(),
        "payload": payload,
    }
    if request_id:
        frame["requestId"] = request_id
    return json.dumps(frame)


def build_error(
    code: str,
    message: str,
    request_id: str | None = None,
    details: dict[str, Any] | None = None,
) -> str:
    """Build compliant protocol server error frame."""
    frame: dict[str, Any] = {
        "protocolVersion": PROTOCOL_VERSION,
        "type": "error",
        "timestamp": datetime.now(UTC).isoformat(),
        "error": {
            "code": code,
            "message": message,
        },
    }
    if details:
        frame["error"]["details"] = details
    if request_id:
        frame["requestId"] = request_id
    return json.dumps(frame)
