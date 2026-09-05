"""WebSocket authentication middleware for Django Channels."""

from typing import Any

from channels.db import database_sync_to_async

from apps.authentication.services import validate_session


@database_sync_to_async
def _get_user_from_token(token: str) -> dict[str, Any] | None:
    """Synchronously validate session in MongoDB and return sanitized user dict."""
    session = validate_session(token)
    if session:
        return {
            "id": str(session.get("user_id")),
            "username": session.get("username"),
            "role": session.get("role", "operator"),
        }
    return None


class WebSocketAuthMiddleware:
    """Extracts session credentials and authenticates WebSocket connections."""

    def __init__(self, inner: Any) -> None:
        self.inner = inner

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> Any:
        # Default unauthenticated user in scope
        scope["user"] = None

        session_token = None

        # 1. Check pre-parsed cookies in scope if available
        if "cookies" in scope and isinstance(scope["cookies"], dict):
            session_token = scope["cookies"].get("revenueos_session")

        # 2. Check raw cookie header if not found
        if not session_token:
            headers = dict(scope.get("headers", []))
            cookie_header = headers.get(b"cookie", b"").decode("utf-8", errors="ignore")
            if cookie_header:
                cookies = [c.strip() for c in cookie_header.split(";")]
                for c in cookies:
                    if c.startswith("revenueos_session="):
                        session_token = c.split("=", 1)[1]
                        break


        # Validate token via async wrapper
        if session_token:
            user_data = await _get_user_from_token(session_token)
            if user_data:
                scope["user"] = user_data

        return await self.inner(scope, receive, send)


def WebSocketAuthMiddlewareStack(inner: Any) -> WebSocketAuthMiddleware:
    """Helper wrapper matching standard Channels middleware style."""
    return WebSocketAuthMiddleware(inner)
