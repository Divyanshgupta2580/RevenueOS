"""URL configuration for RevenueOS."""

from django.http import JsonResponse
from django.urls import path

from apps.authentication.views import login_view, logout_view, me_view


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
    """Readiness probe checking critical service components."""
    return JsonResponse(
        {
            "status": "ready",
            "service": "RevenueOS Backend",
        }
    )


urlpatterns = [
    # Probes
    path("health/", health_check, name="health"),
    path("ready/", readiness_check, name="ready"),
    # Authentication
    path("api/auth/login/", login_view, name="auth_login"),
    path("api/auth/logout/", logout_view, name="auth_logout"),
    path("api/auth/me/", me_view, name="auth_me"),
]
