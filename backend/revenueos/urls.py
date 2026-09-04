"""URL configuration for RevenueOS."""

from django.http import JsonResponse
from django.urls import path

from apps.authentication.views import login_view, logout_view, me_view, register_view
from apps.razorpay_adapter.views import create_order_view, verify_payment_view
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
    path("api/auth/register/", register_view, name="auth_register"),
    path("api/auth/register", register_view, name="auth_register_noslash"),
    path("api/auth/login/", login_view, name="auth_login"),
    path("api/auth/login", login_view, name="auth_login_noslash"),
    path("api/auth/logout/", logout_view, name="auth_logout"),
    path("api/auth/logout", logout_view, name="auth_logout_noslash"),
    path("api/auth/me/", me_view, name="auth_me"),
    path("api/auth/me", me_view, name="auth_me_noslash"),
    # Webhooks
    path("api/webhooks/razorpay/", razorpay_webhook_view, name="razorpay_webhook"),
    # Razorpay Standard Web Checkout
    path("api/create-order", create_order_view, name="create_order"),
    path("api/create-order/", create_order_view, name="create_order_slash"),
    path("api/verify-payment", verify_payment_view, name="verify_payment"),
    path("api/verify-payment/", verify_payment_view, name="verify_payment_slash"),
    path("api/razorpay/create-order", create_order_view, name="rzp_create_order"),
    path("api/razorpay/create-order/", create_order_view, name="rzp_create_order_slash"),
    path("api/razorpay/verify-payment", verify_payment_view, name="rzp_verify_payment"),
    path("api/razorpay/verify-payment/", verify_payment_view, name="rzp_verify_payment_slash"),
]
