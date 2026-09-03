"""ASGI config for RevenueOS project."""

import os

from channels.routing import ProtocolTypeRouter, URLRouter
from channels.security.websocket import AllowedHostsOriginValidator
from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "revenueos.settings")

django_asgi_app = get_asgi_application()

from apps.websocket.auth import WebSocketAuthMiddlewareStack  # noqa: E402
from revenueos.ws_urls import websocket_urlpatterns  # noqa: E402

application = ProtocolTypeRouter(
    {
        "http": django_asgi_app,
        "websocket": AllowedHostsOriginValidator(
            WebSocketAuthMiddlewareStack(URLRouter(websocket_urlpatterns))
        ),
    }
)
