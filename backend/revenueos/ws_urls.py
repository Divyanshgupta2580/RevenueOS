"""WebSocket URL routing for RevenueOS."""

from django.urls import path

from apps.websocket.consumer import RevenueOSConsumer

websocket_urlpatterns = [
    path("ws/v1/app/", RevenueOSConsumer.as_asgi(), name="ws_app_v1"),
]
