"""Tests for Cloudflare Turnstile deployment robustness and hostname validation."""

from unittest.mock import MagicMock, patch
import pytest
from django.test import override_settings

from apps.authentication.services import verify_turnstile_token
from revenueos.settings import _resolve_turnstile_allowed_hostnames


class TestTurnstileHostnameResolution:
    """Verify dynamic resolution of allowed Turnstile hostnames."""

    def test_production_resolves_stable_frontend_host(self) -> None:
        """In production, allowed hostnames strictly match FRONTEND_ORIGIN."""
        hosts = _resolve_turnstile_allowed_hostnames(
            frontend_origin="https://revenueos.vercel.app",
            csrf_origins=["https://revenueos.vercel.app"],
            environment="production",
            env_source={"TURNSTILE_ALLOWED_HOSTNAMES": ""},
        )
        assert hosts == ["revenueos.vercel.app"]
        assert "localhost" not in hosts
        assert "127.0.0.1" not in hosts

    def test_development_includes_local_and_test_hosts(self) -> None:
        """In development/test, localhost, testserver, and example.com are allowed."""
        hosts = _resolve_turnstile_allowed_hostnames(
            frontend_origin="http://localhost:3000",
            csrf_origins=["http://localhost:3000"],
            environment="development",
            env_source={"TURNSTILE_ALLOWED_HOSTNAMES": ""},
        )
        assert "localhost" in hosts
        assert "127.0.0.1" in hosts
        assert "example.com" in hosts

    def test_custom_domain_incorporation(self) -> None:
        """Explicit custom domain via TURNSTILE_ALLOWED_HOSTNAMES is preserved."""
        hosts = _resolve_turnstile_allowed_hostnames(
            frontend_origin="https://revenueos.vercel.app",
            csrf_origins=["https://revenueos.vercel.app"],
            environment="production",
            env_source={"TURNSTILE_ALLOWED_HOSTNAMES": "app.revenueos.io, custom.domain.com"},
        )
        assert "revenueos.vercel.app" in hosts
        assert "app.revenueos.io" in hosts
        assert "custom.domain.com" in hosts


class TestTurnstileVerificationLogic:
    """Verify server-side Turnstile verification and hostname enforcement."""

    def test_missing_token_rejected(self) -> None:
        assert verify_turnstile_token("") is False
        assert verify_turnstile_token(None) is False  # type: ignore

    def test_explicit_invalid_token_rejected(self) -> None:
        assert verify_turnstile_token("2x0000000000000000000000000000000AA") is False
        assert verify_turnstile_token("invalid_token_xyz") is False
        assert verify_turnstile_token("failed") is False

    @patch("requests.post")
    def test_matching_hostname_accepted(self, mock_post: MagicMock) -> None:
        """When Cloudflare returns success and matching production hostname, verification passes."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "success": True,
            "hostname": "revenueos.vercel.app",
            "challenge_ts": "2026-09-05T14:32:01.473Z",
        }
        mock_post.return_value = mock_resp

        with override_settings(
            ENVIRONMENT="production",
            TURNSTILE_SECRET_KEY="0x4AAAAAA_test_secret",
            TURNSTILE_ALLOWED_HOSTNAMES=["revenueos.vercel.app"],
        ):
            result = verify_turnstile_token("real_cf_token_123", remote_ip="1.2.3.4")
            assert result is True

    @patch("requests.post")
    def test_mismatched_deployment_hostname_rejected(self, mock_post: MagicMock) -> None:
        """If token was generated on an ephemeral deployment URL, backend rejects it."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "success": True,
            "hostname": "revenue-c2q8yc0ds-divyansh-guptas-projects-f01c462.vercel.app",
            "challenge_ts": "2026-09-05T14:32:01.473Z",
        }
        mock_post.return_value = mock_resp

        with override_settings(
            ENVIRONMENT="production",
            TURNSTILE_SECRET_KEY="0x4AAAAAA_test_secret",
            TURNSTILE_ALLOWED_HOSTNAMES=["revenueos.vercel.app"],
        ):
            result = verify_turnstile_token("real_cf_token_123")
            assert result is False

    @patch("requests.post")
    def test_arbitrary_hostname_rejected(self, mock_post: MagicMock) -> None:
        """Tokens from random third-party domains are rejected."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "success": True,
            "hostname": "evil-phishing.com",
        }
        mock_post.return_value = mock_resp

        with override_settings(
            ENVIRONMENT="production",
            TURNSTILE_SECRET_KEY="0x4AAAAAA_test_secret",
            TURNSTILE_ALLOWED_HOSTNAMES=["revenueos.vercel.app"],
        ):
            result = verify_turnstile_token("real_cf_token_123")
            assert result is False

    @patch("requests.post")
    def test_network_failure_handled_gracefully(self, mock_post: MagicMock) -> None:
        """Network error or timeout to Cloudflare returns False without throwing unhandled exception."""
        mock_post.side_effect = Exception("Connection timeout to challenges.cloudflare.com")

        with override_settings(
            ENVIRONMENT="production",
            TURNSTILE_SECRET_KEY="0x4AAAAAA_test_secret",
            TURNSTILE_ALLOWED_HOSTNAMES=["revenueos.vercel.app"],
        ):
            result = verify_turnstile_token("real_cf_token_123")
            assert result is False
