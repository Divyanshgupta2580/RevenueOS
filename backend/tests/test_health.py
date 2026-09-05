"""Comprehensive acceptance tests for Liveness (/api/health/) and Readiness (/ready/) probes."""

import time
from unittest.mock import patch

from django.test import Client


def test_api_health_liveness_returns_200() -> None:
    """1. GET /api/health/ returns HTTP 200 with healthy status."""
    client = Client()
    response = client.get("/api/health/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "RevenueOS Backend"
    assert data["version"] == "1.0.0"

    # Also verify backward-compatible /health/ path
    compat_resp = client.get("/health/")
    assert compat_resp.status_code == 200
    assert compat_resp.json()["status"] == "healthy"


def test_readiness_returns_200_when_dependencies_healthy() -> None:
    """2. GET /ready/ returns HTTP 200 when MongoDB is connected."""
    client = Client()
    with patch("apps.database.client.ping_database", return_value=True):
        response = client.get("/ready/")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ready"
        assert data["database"] == "connected"
        assert data["service"] == "RevenueOS Backend"


def test_readiness_fails_cleanly_when_mongodb_unavailable() -> None:
    """3. GET /ready/ returns HTTP 503 degraded when MongoDB connection fails."""
    client = Client()
    with patch("apps.database.client.ping_database", return_value=False):
        response = client.get("/ready/")
        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "degraded"
        assert data["database"] == "disconnected"
        assert data["error"] == "Database connectivity check failed"

    with patch("apps.database.client.ping_database", side_effect=Exception("Simulated socket timeout")):
        response = client.get("/ready/")
        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "degraded"
        assert data["database"] == "disconnected"
        assert data["error"] == "Database connectivity check failed"


def test_liveness_remains_healthy_when_mongodb_unavailable() -> None:
    """4. GET /api/health/ remains HTTP 200 healthy even when MongoDB is completely offline."""
    client = Client()
    with patch("apps.database.client.ping_database", return_value=False):
        response = client.get("/api/health/")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"


def test_no_secrets_appear_in_probe_responses() -> None:
    """5. Zero secrets or sensitive infrastructure strings appear in probe responses."""
    client = Client()
    forbidden_tokens = [
        "GEMINI_API_KEY",
        "RAZORPAY_KEY_SECRET",
        "TURNSTILE_SECRET_KEY",
        "MONGODB_URI",
        "mongodb+srv://",
        "password",
        "secret",
        "Traceback",
    ]

    # Check healthy liveness
    health_content = client.get("/api/health/").content.decode("utf-8")
    for token in forbidden_tokens:
        assert token not in health_content

    # Check healthy readiness
    with patch("apps.database.client.ping_database", return_value=True):
        ready_content = client.get("/ready/").content.decode("utf-8")
        for token in forbidden_tokens:
            assert token not in ready_content

    # Check failing readiness (ensure exception stack traces/credentials are not leaked)
    with patch(
        "apps.database.client.ping_database",
        side_effect=Exception("mongodb+srv://admin:supersecret@cluster0.mongodb.net/"),
    ):
        failing_ready = client.get("/ready/").content.decode("utf-8")
        for token in forbidden_tokens:
            assert token not in failing_ready


def test_unauthenticated_access_allowed() -> None:
    """6. Probes allow unauthenticated access without sessions or cookies."""
    client = Client()
    health_resp = client.get("/api/health/")
    assert health_resp.status_code == 200

    with patch("apps.database.client.ping_database", return_value=True):
        ready_resp = client.get("/ready/")
        assert ready_resp.status_code == 200


def test_probe_response_time_remains_lightweight() -> None:
    """7. Liveness probe responds in sub-millisecond to low millisecond time."""
    client = Client()
    start_time = time.perf_counter()
    response = client.get("/api/health/")
    duration_ms = (time.perf_counter() - start_time) * 1000
    assert response.status_code == 200
    assert duration_ms < 50.0  # Must be fast for load balancers


def test_no_external_gemini_or_razorpay_calls_in_probes() -> None:
    """8. Probe endpoints do not invoke Gemini API or Razorpay API."""
    client = Client()
    with patch("apps.brain.provider.GeminiProvider.generate_recommendation") as mock_gemini, patch(
        "apps.razorpay_adapter.adapter.RazorpayAdapter.create_payment_link"
    ) as mock_rzp:
        _ = client.get("/api/health/")
        with patch("apps.database.client.ping_database", return_value=True):
            _ = client.get("/ready/")

        assert not mock_gemini.called
        assert not mock_rzp.called


def test_health_ignores_invalid_auth_and_csrf_headers() -> None:
    """9. Health endpoint succeeds even if invalid auth, session, or csrf headers are sent."""
    client = Client()

    # Invalid Bearer
    resp = client.get("/api/health/", HTTP_AUTHORIZATION="Bearer invalid_token_12345")
    assert resp.status_code == 200
    assert resp.json()["status"] == "healthy"

    # Invalid Cookie
    client.cookies["sessionid"] = "invalid_session_id"
    resp2 = client.get("/api/health/")
    assert resp2.status_code == 200
    assert resp2.json()["status"] == "healthy"

    # Invalid CSRF header
    resp3 = client.get("/api/health/", HTTP_X_CSRFTOKEN="invalid_csrf")
    assert resp3.status_code == 200
    assert resp3.json()["status"] == "healthy"

