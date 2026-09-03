"""Test health and readiness endpoints."""

from django.test import Client


def test_health_check() -> None:
    """Ensure /health/ returns 200 with healthy status."""
    client = Client()
    response = client.get("/health/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "RevenueOS Backend"


def test_readiness_check() -> None:
    """Ensure /ready/ returns 200 with ready status."""
    client = Client()
    response = client.get("/ready/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ready"
