"""Tests for email health check functionality."""

import socket
from unittest.mock import MagicMock, patch

import pytest
from django.test import override_settings

from infra.email.health import (
    _check_resend_health,
    check_email_health,
    check_email_provider_health,
)

# --- check_email_provider_health ---


class TestCheckResendHealth:
    """Tests for _check_resend_health (Resend provider)."""

    def test_resend_healthy_via_provider_check(self):
        """Resend provider returns healthy when API call succeeds."""
        with patch("infra.email.health._check_resend_health") as mock_resend:
            mock_resend.return_value = {"status": "healthy", "provider": "resend"}
            result = check_email_provider_health("resend", api_key="re_test_key")
            assert result["status"] == "healthy"
            assert result["provider"] == "resend"

    def test_resend_unhealthy_on_api_error(self):
        """Resend provider returns unhealthy when API call raises exception."""
        with patch("infra.email.health._check_resend_health") as mock_resend:
            mock_resend.return_value = {
                "status": "unhealthy",
                "provider": "resend",
                "error": "API error",
            }
            result = check_email_provider_health("resend", api_key="re_test_key")
            assert result["status"] == "unhealthy"
            assert result["provider"] == "resend"

    def test_resend_unhealthy_without_api_key(self):
        """Resend provider returns unhealthy when API key is missing."""
        result = _check_resend_health(None)
        assert result["status"] == "unhealthy"
        assert result["provider"] == "resend"
        assert "API key" in result["error"]

    def test_resend_unhealthy_with_empty_api_key(self):
        """Resend provider returns unhealthy when API key is empty."""
        result = _check_resend_health("")
        assert result["status"] == "unhealthy"
        assert result["provider"] == "resend"

    def test_resend_api_call_succeeds(self):
        """Direct test: _check_resend_health succeeds when resend API works."""
        mock_resend = MagicMock()
        mock_resend.Domains.list.return_value = [{"id": "d1"}]
        with patch.dict("sys.modules", {"resend": mock_resend}):
            result = _check_resend_health("re_test_key")
        assert result["status"] == "healthy"
        assert result["provider"] == "resend"

    def test_resend_api_call_fails(self):
        """Direct test: _check_resend_health returns unhealthy on API exception."""
        mock_resend = MagicMock()
        mock_resend.Domains.list.side_effect = Exception("API error happened")
        with patch.dict("sys.modules", {"resend": mock_resend}):
            result = _check_resend_health("re_test_key")
        assert result["status"] == "unhealthy"
        assert result["provider"] == "resend"
        assert "error" in result


class TestCheckSmtpHealth:
    """Tests for check_email_provider_health with smtp/ses providers."""

    @patch("infra.email.health.socket.create_connection")
    @override_settings(EMAIL_HOST="smtp.example.com", EMAIL_PORT=587)
    def test_smtp_healthy(self, mock_conn):
        """SMTP provider returns healthy when TCP connection succeeds."""
        mock_conn.return_value.__enter__ = MagicMock()
        mock_conn.return_value.__exit__ = MagicMock(return_value=False)
        result = check_email_provider_health("smtp")
        assert result["status"] == "healthy"
        assert result["provider"] == "smtp"

    @patch(
        "infra.email.health.socket.create_connection", side_effect=ConnectionRefusedError("refused")
    )
    @override_settings(
        EMAIL_HOST="smtp.example.com", EMAIL_PORT=587, EMAIL_HOST_USER="user@test.com"
    )
    def test_smtp_unhealthy_connection_refused(self, mock_conn):
        """SMTP provider returns unhealthy when TCP connection is refused."""
        result = check_email_provider_health("smtp")
        assert result["status"] == "unhealthy"
        assert result["provider"] == "smtp"
        assert "error" in result
        assert result["key_status"] == "configured"

    @patch("infra.email.health.socket.create_connection", side_effect=socket.timeout("timed out"))
    @override_settings(EMAIL_HOST="smtp.example.com", EMAIL_PORT=587, EMAIL_HOST_USER="")
    def test_smtp_unhealthy_timeout(self, mock_conn):
        """SMTP provider returns unhealthy when TCP connection times out."""
        result = check_email_provider_health("smtp")
        assert result["status"] == "unhealthy"
        assert "error" in result
        assert result["key_status"] == "not_configured"

    @override_settings(EMAIL_HOST="", EMAIL_PORT=587)
    def test_smtp_unhealthy_no_host_configured(self):
        """SMTP provider returns unhealthy when EMAIL_HOST is not configured."""
        result = check_email_provider_health("smtp")
        assert result["status"] == "unhealthy"
        assert "not configured" in result["error"]

    @patch("infra.email.health.socket.create_connection")
    @override_settings(EMAIL_HOST="email-smtp.us-east-1.amazonaws.com", EMAIL_PORT=587)
    def test_ses_healthy(self, mock_conn):
        """SES provider returns healthy when TCP connection succeeds."""
        mock_conn.return_value.__enter__ = MagicMock()
        mock_conn.return_value.__exit__ = MagicMock(return_value=False)
        result = check_email_provider_health("ses")
        assert result["status"] == "healthy"
        # SES uses the same TCP check as SMTP, so provider name is "smtp"
        assert result["provider"] == "smtp"


class TestCheckConsoleHealth:
    """Tests for check_email_provider_health with console provider."""

    def test_console_always_healthy(self):
        """Console provider always returns healthy."""
        result = check_email_provider_health("console")
        assert result["status"] == "healthy"
        assert result["provider"] == "console"
        assert "note" in result

    def test_console_healthy_regardless_of_env(self):
        """Console provider is always healthy regardless of environment."""
        result = check_email_provider_health("console")
        assert result["status"] == "healthy"


class TestCheckUnknownProvider:
    """Tests for check_email_provider_health with unknown provider."""

    def test_unknown_provider_returns_unhealthy(self):
        """Unknown provider name returns unhealthy with unknown provider error."""
        result = check_email_provider_health("unknown_provider")
        assert result["status"] == "unhealthy"
        assert result["provider"] == "unknown_provider"
        assert result["error"] == "unknown provider"

    def test_mixed_case_provider_uses_lowercase(self):
        """Provider name is case-insensitive."""
        result = check_email_provider_health("Console")
        assert result["status"] == "healthy"

    def test_provider_with_whitespace(self):
        """Provider name with whitespace is trimmed."""
        result = check_email_provider_health("  console  ")
        assert result["status"] == "healthy"


# --- check_email_health ---


class TestCheckEmailHealth:
    """Tests for check_email_health (integration-level)."""

    @patch("infra.email.health._get_email_settings")
    def test_primary_only_console(self, mock_settings):
        """When no fallback is configured, returns single provider status."""
        mock_email = MagicMock()
        mock_email.provider = "console"
        mock_email.resend_api_key = ""
        mock_email.fallback_provider = ""
        mock_settings.return_value = mock_email

        result = check_email_health()
        assert "email" in result
        assert result["email"]["status"] == "healthy"

    @patch("infra.email.health.check_email_provider_health")
    @patch("infra.email.health._get_email_settings")
    def test_primary_and_fallback_both_checked(self, mock_settings, mock_provider_health):
        """When fallback_provider is set, both primary and fallback are checked."""
        mock_email = MagicMock()
        mock_email.provider = "resend"
        mock_email.resend_api_key = "re_test"
        mock_email.fallback_provider = "smtp"
        mock_settings.return_value = mock_email

        mock_provider_health.side_effect = [
            {"status": "healthy", "provider": "resend"},
            {"status": "healthy", "provider": "smtp"},
        ]

        result = check_email_health()

        assert "email" in result
        assert "primary" in result["email"]
        assert "fallback" in result["email"]
        assert result["email"]["primary"]["provider"] == "resend"
        assert result["email"]["fallback"]["provider"] == "smtp"

    @patch("infra.email.health.check_email_provider_health")
    @patch("infra.email.health._get_email_settings")
    def test_fallback_empty_string_only_checks_primary(self, mock_settings, mock_provider_health):
        """When fallback_provider is empty string, only primary is checked."""
        mock_email = MagicMock()
        mock_email.provider = "console"
        mock_email.resend_api_key = ""
        mock_email.fallback_provider = ""
        mock_settings.return_value = mock_email

        mock_provider_health.return_value = {"status": "healthy", "provider": "console"}

        result = check_email_health()

        assert "email" in result
        # Should NOT have "primary"/"fallback" keys - direct status
        assert "primary" not in result["email"]
        assert result["email"]["status"] == "healthy"
        # Should only have been called once (no fallback)
        assert mock_provider_health.call_count == 1

    @patch("infra.email.health._get_email_settings", side_effect=Exception("unexpected"))
    def test_check_email_health_catches_exceptions(self, mock_settings):
        """check_email_health catches all exceptions and returns unhealthy."""
        result = check_email_health()

        assert "email" in result
        assert result["email"]["status"] == "unhealthy"
        assert "error" in result["email"]


# --- HealthCheckView integration ---


@pytest.mark.django_db
class TestHealthCheckViewEmail:
    """Tests for health endpoint returning email component."""

    @patch("apps.core.views.health.check_email_health")
    def test_health_endpoint_returns_email_component(self, mock_email_health, client):
        """Health endpoint includes email component in JSON response."""
        mock_email_health.return_value = {
            "email": {"status": "healthy", "provider": "console"},
        }
        response = client.get("/health/")

        assert response.status_code == 200
        data = response.json()
        assert "email" in data.get("components", {})

    @patch("apps.core.views.health.check_email_health")
    def test_health_endpoint_503_when_email_unhealthy(self, mock_email_health, client):
        """Health endpoint returns 503 when email provider is unhealthy."""
        mock_email_health.return_value = {
            "email": {
                "status": "unhealthy",
                "provider": "resend",
                "error": "API error",
            },
        }
        response = client.get("/health/")

        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "unhealthy"
        assert "email" in data.get("components", {})

    @patch("apps.core.views.health.check_email_health")
    def test_health_endpoint_200_when_email_healthy(self, mock_email_health, client):
        """Health endpoint returns 200 when email provider is healthy."""
        mock_email_health.return_value = {
            "email": {"status": "healthy", "provider": "console"},
        }
        response = client.get("/health/")

        data = response.json()
        email_component = data.get("components", {}).get("email", {})
        assert email_component.get("status") == "healthy"

    @patch("apps.core.views.health.check_email_health")
    def test_health_endpoint_with_fallback_providers(self, mock_email_health, client):
        """Health endpoint shows primary and fallback when both configured."""
        mock_email_health.return_value = {
            "email": {
                "primary": {"status": "healthy", "provider": "resend"},
                "fallback": {"status": "healthy", "provider": "smtp"},
            },
        }
        response = client.get("/health/")

        assert response.status_code == 200
        data = response.json()
        email_component = data.get("components", {}).get("email", {})
        assert "primary" in email_component
        assert "fallback" in email_component

    @patch("apps.core.views.health.check_email_health")
    def test_health_endpoint_503_when_fallback_unhealthy(self, mock_email_health, client):
        """Health endpoint returns 503 when fallback provider is unhealthy."""
        mock_email_health.return_value = {
            "email": {
                "primary": {"status": "healthy", "provider": "resend"},
                "fallback": {
                    "status": "unhealthy",
                    "provider": "smtp",
                    "error": "connection failed",
                },
            },
        }
        response = client.get("/health/")

        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "unhealthy"
