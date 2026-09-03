"""URL configuration for RevenueOS."""

from django.http import JsonResponse
from django.urls import path

from apps.authentication.views import login_view, logout_view, me_view
from apps.webhooks.views import razorpay_webhook_view


def health_check(request) -> JsonResponse:
    """Unauthenticated health endpoint for deployment probes."""
    return JsonResponse(
        {
            "status": "healthy",
            "service": "RevenueOS Backend",
            "version": "1.0.0",
        }
    )


def readiness_check(request) -> JsonResponse:
    """Readiness probe checking critical service components and database connection."""
    from apps.database.client import get_database
    try:
        db = get_database()
        # Test collection access
        _ = db.users.count_documents({})
        return JsonResponse(
            {
                "status": "ready",
                "service": "RevenueOS Backend",
                "database": "connected",
            },
            status=200,
        )
    except Exception as exc:
        return JsonResponse(
            {
                "status": "degraded",
                "service": "RevenueOS Backend",
                "database": "disconnected",
                "error": str(exc),
            },
            status=503,
        )


urlpatterns = [
    # Probes
    path("health/", health_check, name="health"),
    path("ready/", readiness_check, name="ready"),
    # Authentication
    path("api/auth/login/", login_view, name="auth_login"),
    path("api/auth/logout/", logout_view, name="auth_logout"),
    path("api/auth/me/", me_view, name="auth_me"),
    # Webhooks
    path("api/webhooks/razorpay/", razorpay_webhook_view, name="razorpay_webhook"),
]
