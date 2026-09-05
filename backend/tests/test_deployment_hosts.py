"""Automated tests for Render deployment, ALLOWED_HOSTS resolution, port binding, and health probes."""

from pathlib import Path
from unittest.mock import patch

import yaml
from django.test import Client, SimpleTestCase, override_settings

from revenueos.settings import _resolve_allowed_hosts


class TestAllowedHostsResolution(SimpleTestCase):
    """Verifies environment-driven dynamic ALLOWED_HOSTS resolution."""

    def test_localhost_accepted_in_development(self) -> None:
        """2. Localhost accepted in development."""
        hosts = _resolve_allowed_hosts({})
        assert "localhost" in hosts
        assert "127.0.0.1" in hosts
        assert "0.0.0.0" in hosts
        assert "testserver" in hosts
        assert "::1" in hosts

    def test_render_hostname_accepted_through_env(self) -> None:
        """1. Render hostname accepted through RENDER_EXTERNAL_HOSTNAME."""
        test_render_host = "revenueos-backend-f81a.onrender.com"
        hosts = _resolve_allowed_hosts({"RENDER_EXTERNAL_HOSTNAME": test_render_host})
        assert test_render_host in hosts

    def test_no_allowed_hosts_wildcard(self) -> None:
        """10. No ALLOWED_HOSTS wildcard."""
        hosts = _resolve_allowed_hosts({"DJANGO_ALLOWED_HOSTS": "*, evil.com, localhost"})
        assert "*" not in hosts

    def test_render_external_url_accepted(self) -> None:
        """Render external URL is parsed safely."""
        hosts = _resolve_allowed_hosts({"RENDER_EXTERNAL_URL": "https://revenueos-backend-f81a.onrender.com"})
        assert "revenueos-backend-f81a.onrender.com" in hosts

    def test_explicit_hosts_merged_safely(self) -> None:
        """Explicit custom domains are accepted and merged without duplicates."""
        hosts = _resolve_allowed_hosts(
            {
                "DJANGO_ALLOWED_HOSTS": "api.revenueos.io, custom.org",
                "RENDER_EXTERNAL_HOSTNAME": "revenueos-backend-f81a.onrender.com",
            }
        )
        assert "api.revenueos.io" in hosts
        assert "custom.org" in hosts
        assert "revenueos-backend-f81a.onrender.com" in hosts
        assert "localhost" in hosts


class TestDeploymentSecurityAndProbes(SimpleTestCase):
    """Verifies security controls, host header rejection, and probe stability."""

    def test_invalid_arbitrary_host_rejected(self) -> None:
        """3. Invalid arbitrary host rejected."""
        client = Client()
        # Request with disallowed host must return HTTP 400 Bad Request
        response = client.get("/api/health/", HTTP_HOST="evil.example.com")
        assert response.status_code == 400

    def test_api_health_returns_200_with_render_host_header(self) -> None:
        """4. /api/health/ returns 200 with Render Host header."""
        render_host = "revenueos-backend-f81a.onrender.com"
        with override_settings(ALLOWED_HOSTS=_resolve_allowed_hosts({"RENDER_EXTERNAL_HOSTNAME": render_host})):
            client = Client()
            response = client.get("/api/health/", HTTP_HOST=render_host)
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "healthy"
            assert data["service"] == "RevenueOS Backend"

    def test_api_health_remains_unauthenticated(self) -> None:
        """5. /api/health/ remains unauthenticated."""
        client = Client()
        response = client.get("/api/health/")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"

    def test_api_health_remains_dependency_free(self) -> None:
        """6. /api/health/ remains dependency-free (no DB, Gemini, or Razorpay)."""
        client = Client()
        with patch("apps.database.client.ping_database") as mock_db, patch(
            "apps.brain.provider.GeminiProvider.generate_recommendation"
        ) as mock_gemini, patch(
            "apps.razorpay_adapter.adapter.RazorpayAdapter.create_payment_link"
        ) as mock_rzp:
            response = client.get("/api/health/")
            assert response.status_code == 200
            assert not mock_db.called
            assert not mock_gemini.called
            assert not mock_rzp.called

    def test_readiness_remains_correct(self) -> None:
        """7. /ready/ remains correct (200 healthy, 503 degraded)."""
        client = Client()
        with patch("apps.database.client.ping_database", return_value=True):
            ready_resp = client.get("/ready/")
            assert ready_resp.status_code == 200
            assert ready_resp.json()["status"] == "ready"

        with patch("apps.database.client.ping_database", return_value=False):
            degraded_resp = client.get("/ready/")
            assert degraded_resp.status_code == 503
            assert degraded_resp.json()["status"] == "degraded"


class TestRenderConfiguration(SimpleTestCase):
    """Verifies render.yaml and deployment constraints."""

    def test_port_is_not_hardcoded(self) -> None:
        """8. PORT is not hardcoded in render.yaml or settings."""
        render_yaml_path = Path(__file__).resolve().parent.parent.parent / "render.yaml"
        assert render_yaml_path.exists()
        content = render_yaml_path.read_text(encoding="utf-8")
        assert "10000" not in content
        assert "8000" not in content
        assert "3000" not in content

    def test_start_command_uses_env_port(self) -> None:
        """9. Start command uses $PORT with daphne."""
        render_yaml_path = Path(__file__).resolve().parent.parent.parent / "render.yaml"
        assert render_yaml_path.exists()
        with open(render_yaml_path, encoding="utf-8") as f:
            data = yaml.safe_load(f)

        service = data["services"][0]
        assert service["startCommand"] == "daphne -b 0.0.0.0 -p $PORT revenueos.asgi:application"
        assert service["healthCheckPath"] == "/api/health/"
        assert service["rootDir"] == "backend"
        assert service["buildCommand"] == "pip install -r requirements.txt"
