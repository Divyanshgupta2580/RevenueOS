"""WebSocket authentication middleware for Django Channels."""

from typing import Any

from apps.authentication.services import validate_session


class WebSocketAuthMiddleware:
    """Extracts session cookie and authenticates WebSocket connections."""

    def __init__(self, inner: Any) -> None:
        self.inner = inner

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> Any:
        # Default unauthenticated user in scope
        scope["user"] = None

        headers = dict(scope.get("headers", []))
        cookie_header = headers.get(b"cookie", b"").decode("utf-8")

        session_token = None
        if cookie_header:
            cookies = [c.strip() for c in cookie_header.split(";")]
            for c in cookies:
                if c.startswith("revenueos_session="):
                    session_token = c.split("=", 1)[1]
                    break

        if session_token:
            session = validate_session(session_token)
            if session:
                scope["user"] = {
                    "id": session.get("user_id"),
                    "username": session.get("username"),
                    "role": session.get("role", "operator"),
                }

        return await self.inner(scope, receive, send)


def WebSocketAuthMiddlewareStack(inner: Any) -> WebSocketAuthMiddleware:
    """Helper wrapper matching standard Channels middleware style."""
    return WebSocketAuthMiddleware(inner)
