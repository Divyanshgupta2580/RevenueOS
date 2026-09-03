"""URL configuration for RevenueOS."""

from django.http import JsonResponse
from django.urls import path


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
    path("health/", health_check, name="health"),
    path("ready/", readiness_check, name="ready"),
]
