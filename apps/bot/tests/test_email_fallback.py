"""Tests for email fallback logic in send_transactional_email."""

from unittest.mock import MagicMock

from apps.bot.email_service import send_transactional_email
from infra.email.factory import (
    EmailProviderConfigurationError,
    UnknownEmailProviderError,
    get_email_fallback_provider,
)
from infra.email.protocols import EmailSendResult

# --- Helper classes ---


class RecordingProvider:
    """Provider that records calls and returns a preset result."""

    def __init__(self, result: EmailSendResult) -> None:
        self._result = result
        self.calls: list[dict[str, object]] = []

    def send(self, **kwargs) -> EmailSendResult:
        self.calls.append(kwargs)
        return self._result


class FailingProvider:
    """Provider that raises an exception on send."""

    def __init__(self, error: Exception) -> None:
        self._error = error
        self.calls: list[dict[str, object]] = []

    def send(self, **kwargs) -> EmailSendResult:
        self.calls.append(kwargs)
        raise self._error


# --- get_email_fallback_provider tests ---


class TestGetEmailFallbackProvider:
    """Tests for get_email_fallback_provider factory function."""

    def test_returns_none_when_fallback_empty(self, mocker):
        """When EMAIL_FALLBACK_PROVIDER is empty string, returns None."""
        mock_settings = MagicMock()
        mock_settings.email.fallback_provider = ""
        mocker.patch("infra.email.factory.settings", mock_settings)

        result = get_email_fallback_provider()

        assert result is None

    def test_returns_provider_when_fallback_configured(self, mocker):
        """When EMAIL_FALLBACK_PROVIDER is set to a valid provider, returns that provider."""
        mock_settings = MagicMock()
        mock_settings.email.fallback_provider = "smtp"
        mocker.patch("infra.email.factory.settings", mock_settings)

        result = get_email_fallback_provider()

        assert result is not None

    def test_returns_none_on_unknown_provider_error(self, mocker):
        """When EMAIL_FALLBACK_PROVIDER is an unknown value, logs warning and returns None."""
        mock_settings = MagicMock()
        mock_settings.email.fallback_provider = "invalid_provider"
        mock_settings.email.provider = "console"
        mocker.patch("infra.email.factory.settings", mock_settings)

        result = get_email_fallback_provider()

        assert result is None

    def test_returns_none_on_configuration_error(self, mocker):
        """When fallback provider is misconfigured (e.g. resend without api key), returns None."""
        mock_settings = MagicMock()
        mock_settings.email.fallback_provider = "resend"
        mock_settings.email.resend_api_key = ""
        mock_settings.email.provider = "console"
        mocker.patch("infra.email.factory.settings", mock_settings)

        result = get_email_fallback_provider()

        assert result is None

    def test_logs_warning_on_config_error(self, mocker):
        """When fallback is misconfigured, logs email_fallback_provider_config_error."""
        mock_settings = MagicMock()
        mock_settings.email.fallback_provider = "invalid_provider"
        mock_settings.email.provider = "console"
        mocker.patch("infra.email.factory.settings", mock_settings)
        warning_spy = mocker.patch("infra.email.factory.logger.warning")

        get_email_fallback_provider()

        warning_spy.assert_called_once()
        assert warning_spy.call_args[0][0] == "email_fallback_provider_config_error"


# --- Fallback in send_transactional_email tests ---


class TestFallbackOnPrimaryError:
    """Tests for automatic fallback when primary provider returns status=error."""

    def test_primary_sends_successfully_no_fallback(self, mocker):
        """When primary sends successfully, no fallback is attempted."""
        provider = RecordingProvider(
            EmailSendResult(status="sent", provider="resend", message_id="msg-1", error_code=None)
        )
        mocker.patch("apps.bot.email_service.get_email_provider", return_value=provider)
        fallback_mock = mocker.patch("apps.bot.email_service.get_email_fallback_provider")

        result = send_transactional_email(
            subject="Test",
            message="body",
            recipient_list=["user@test.com"],
            event_type="transactional",
        )

        assert result["status"] == "sent"
        assert result["provider"] == "resend"
        fallback_mock.assert_not_called()

    def test_primary_fails_fallback_sends_successfully(self, mocker):
        """When primary fails and fallback succeeds, returns fallback result (D-04)."""
        primary_provider = RecordingProvider(
            EmailSendResult(
                status="error", provider="resend", message_id=None, error_code="api_error"
            )
        )
        fallback_provider = RecordingProvider(
            EmailSendResult(
                status="sent", provider="smtp", message_id="msg-fallback", error_code=None
            )
        )

        mock_settings = MagicMock()
        mock_settings.email.fallback_provider = "smtp"
        mocker.patch("apps.bot.email_service.app_settings", mock_settings)
        mocker.patch("apps.bot.email_service.get_email_provider", return_value=primary_provider)
        mocker.patch(
            "apps.bot.email_service.get_email_fallback_provider", return_value=fallback_provider
        )

        result = send_transactional_email(
            subject="Test",
            message="body",
            recipient_list=["user@test.com"],
            event_type="email_confirmation",
        )

        assert result["status"] == "sent"
        assert result["provider"] == "smtp"
        assert result["message_id"] == "msg-fallback"

    def test_primary_fails_fallback_also_fails(self, mocker):
        """When both primary and fallback fail, returns fallback error result."""
        primary_provider = RecordingProvider(
            EmailSendResult(
                status="error", provider="resend", message_id=None, error_code="api_error"
            )
        )
        fallback_provider = RecordingProvider(
            EmailSendResult(
                status="error", provider="smtp", message_id=None, error_code="connection_failed"
            )
        )

        mock_settings = MagicMock()
        mock_settings.email.fallback_provider = "smtp"
        mocker.patch("apps.bot.email_service.app_settings", mock_settings)
        mocker.patch("apps.bot.email_service.get_email_provider", return_value=primary_provider)
        mocker.patch(
            "apps.bot.email_service.get_email_fallback_provider", return_value=fallback_provider
        )

        result = send_transactional_email(
            subject="Test",
            message="body",
            recipient_list=["user@test.com"],
            event_type="offline_alert",
        )

        assert result["status"] == "error"
        assert result["provider"] == "smtp"
        assert result["error_code"] == "connection_failed"

    def test_primary_fails_no_fallback_configured(self, mocker):
        """When primary fails and no fallback is configured, returns primary error (D-03 backward compat)."""
        provider = RecordingProvider(
            EmailSendResult(
                status="error", provider="resend", message_id=None, error_code="api_error"
            )
        )

        mock_settings = MagicMock()
        mock_settings.email.fallback_provider = ""
        mocker.patch("apps.bot.email_service.app_settings", mock_settings)
        mocker.patch("apps.bot.email_service.get_email_provider", return_value=provider)

        result = send_transactional_email(
            subject="Test",
            message="body",
            recipient_list=["user@test.com"],
            event_type="transactional",
        )

        assert result["status"] == "error"
        assert result["provider"] == "resend"
        assert result["error_code"] == "api_error"

    def test_primary_fails_fallback_misconfigured_returns_primary_error(self, mocker):
        """When primary fails and fallback is misconfigured, returns primary error result."""
        provider = RecordingProvider(
            EmailSendResult(
                status="error", provider="resend", message_id=None, error_code="api_error"
            )
        )

        mock_settings = MagicMock()
        mock_settings.email.fallback_provider = "invalid"
        mocker.patch("apps.bot.email_service.app_settings", mock_settings)
        mocker.patch("apps.bot.email_service.get_email_provider", return_value=provider)
        mocker.patch("apps.bot.email_service.get_email_fallback_provider", return_value=None)

        result = send_transactional_email(
            subject="Test",
            message="body",
            recipient_list=["user@test.com"],
            event_type="transactional",
        )

        assert result["status"] == "error"
        assert result["provider"] == "resend"
        assert result["error_code"] == "api_error"


class TestFallbackOnExceptionErrors:
    """Tests for fallback triggering on ALL error types (D-02)."""

    def test_unknown_provider_error_triggers_fallback(self, mocker):
        """When primary raises UnknownEmailProviderError, fallback is attempted (D-02)."""
        fallback_provider = RecordingProvider(
            EmailSendResult(
                status="sent", provider="smtp", message_id="msg-fb", error_code=None
            )
        )

        mock_settings = MagicMock()
        mock_settings.email.fallback_provider = "smtp"
        mocker.patch("apps.bot.email_service.app_settings", mock_settings)
        mocker.patch(
            "apps.bot.email_service.get_email_provider",
            side_effect=UnknownEmailProviderError("bad provider"),
        )
        mocker.patch(
            "apps.bot.email_service.get_email_fallback_provider", return_value=fallback_provider
        )

        result = send_transactional_email(
            subject="Test",
            message="body",
            recipient_list=["user@test.com"],
            event_type="transactional",
        )

        assert result["status"] == "sent"
        assert result["provider"] == "smtp"
        assert result["message_id"] == "msg-fb"

    def test_configuration_error_triggers_fallback(self, mocker):
        """When primary raises EmailProviderConfigurationError, fallback is attempted (D-02)."""
        fallback_provider = RecordingProvider(
            EmailSendResult(
                status="sent", provider="smtp", message_id="msg-fb", error_code=None
            )
        )

        mock_settings = MagicMock()
        mock_settings.email.fallback_provider = "smtp"
        mocker.patch("apps.bot.email_service.app_settings", mock_settings)
        mocker.patch(
            "apps.bot.email_service.get_email_provider",
            side_effect=EmailProviderConfigurationError("RESEND_API_KEY missing"),
        )
        mocker.patch(
            "apps.bot.email_service.get_email_fallback_provider", return_value=fallback_provider
        )

        result = send_transactional_email(
            subject="Test",
            message="body",
            recipient_list=["user@test.com"],
            event_type="email_confirmation",
        )

        assert result["status"] == "sent"
        assert result["provider"] == "smtp"

    def test_generic_exception_triggers_fallback(self, mocker):
        """When primary raises a generic Exception, fallback is attempted (D-02)."""
        fallback_provider = RecordingProvider(
            EmailSendResult(
                status="sent", provider="smtp", message_id="msg-fb", error_code=None
            )
        )

        mock_settings = MagicMock()
        mock_settings.email.fallback_provider = "smtp"
        mocker.patch("apps.bot.email_service.app_settings", mock_settings)
        mocker.patch(
            "apps.bot.email_service.get_email_provider",
            side_effect=RuntimeError("unexpected error"),
        )
        mocker.patch(
            "apps.bot.email_service.get_email_fallback_provider", return_value=fallback_provider
        )

        result = send_transactional_email(
            subject="Test",
            message="body",
            recipient_list=["user@test.com"],
            event_type="offline_alert",
        )

        assert result["status"] == "sent"
        assert result["provider"] == "smtp"

    def test_unknown_provider_error_no_fallback_returns_error(self, mocker):
        """When primary raises UnknownEmailProviderError and no fallback, returns error dict."""
        mock_settings = MagicMock()
        mock_settings.email.fallback_provider = ""
        mocker.patch("apps.bot.email_service.app_settings", mock_settings)
        mocker.patch(
            "apps.bot.email_service.get_email_provider",
            side_effect=UnknownEmailProviderError("bad provider"),
        )

        result = send_transactional_email(
            subject="Test",
            message="body",
            recipient_list=["user@test.com"],
            event_type="transactional",
        )

        assert result["status"] == "error"
        assert result["error_code"] == "unknown_provider"

    def test_configuration_error_no_fallback_returns_error(self, mocker):
        """When primary raises EmailProviderConfigurationError and no fallback, returns error dict."""
        mock_settings = MagicMock()
        mock_settings.email.fallback_provider = ""
        mocker.patch("apps.bot.email_service.app_settings", mock_settings)
        mocker.patch(
            "apps.bot.email_service.get_email_provider",
            side_effect=EmailProviderConfigurationError("misconfigured"),
        )

        result = send_transactional_email(
            subject="Test",
            message="body",
            recipient_list=["user@test.com"],
            event_type="transactional",
        )

        assert result["status"] == "error"
        assert result["error_code"] == "provider_misconfigured"


class TestFallbackLogging:
    """Tests for fallback event logging (D-05, D-12)."""

    def test_email_fallback_triggered_logged_before_fallback(self, mocker):
        """email_fallback_triggered is logged BEFORE fallback attempt (D-12, D-05)."""
        primary_provider = RecordingProvider(
            EmailSendResult(
                status="error", provider="resend", message_id=None, error_code="api_error"
            )
        )
        fallback_provider = RecordingProvider(
            EmailSendResult(status="sent", provider="smtp", message_id="msg-2", error_code=None)
        )

        mock_settings = MagicMock()
        mock_settings.email.fallback_provider = "smtp"
        mocker.patch("apps.bot.email_service.app_settings", mock_settings)
        mocker.patch("apps.bot.email_service.get_email_provider", return_value=primary_provider)
        mocker.patch(
            "apps.bot.email_service.get_email_fallback_provider", return_value=fallback_provider
        )
        info_spy = mocker.patch("apps.bot.email_service.logger.info")

        send_transactional_email(
            subject="Test",
            message="body",
            recipient_list=["user@test.com"],
            event_type="email_confirmation",
        )

        triggered_calls = [
            c for c in info_spy.call_args_list if c[0][0] == "email_fallback_triggered"
        ]
        assert len(triggered_calls) == 1
        call_kwargs = triggered_calls[0][1]
        assert call_kwargs["primary_provider"] == "resend"
        assert call_kwargs["fallback_provider"] == "smtp"
        assert call_kwargs["reason"] == "api_error"
        assert call_kwargs["event_type"] == "email_confirmation"

    def test_email_fallback_failed_logged_when_both_fail(self, mocker):
        """email_fallback_failed is logged when both primary and fallback fail."""
        primary_provider = RecordingProvider(
            EmailSendResult(
                status="error", provider="resend", message_id=None, error_code="api_error"
            )
        )
        fallback_provider = RecordingProvider(
            EmailSendResult(
                status="error", provider="smtp", message_id=None, error_code="connection_failed"
            )
        )

        mock_settings = MagicMock()
        mock_settings.email.fallback_provider = "smtp"
        mocker.patch("apps.bot.email_service.app_settings", mock_settings)
        mocker.patch("apps.bot.email_service.get_email_provider", return_value=primary_provider)
        mocker.patch(
            "apps.bot.email_service.get_email_fallback_provider", return_value=fallback_provider
        )
        error_spy = mocker.patch("apps.bot.email_service.logger.error")

        send_transactional_email(
            subject="Test",
            message="body",
            recipient_list=["user@test.com"],
            event_type="email_confirmation",
        )

        failed_calls = [
            c for c in error_spy.call_args_list if c[0][0] == "email_fallback_failed"
        ]
        assert len(failed_calls) == 1
        call_kwargs = failed_calls[0][1]
        assert call_kwargs["primary_provider"] == "resend"
        assert call_kwargs["fallback_provider"] == "smtp"
        assert call_kwargs["fallback_error"] == "connection_failed"
        assert call_kwargs["event_type"] == "email_confirmation"

    def test_email_fallback_provider_unavailable_logged_when_misconfigured(self, mocker):
        """email_fallback_provider_unavailable warning logged when fallback is misconfigured."""
        primary_provider = RecordingProvider(
            EmailSendResult(
                status="error", provider="resend", message_id=None, error_code="api_error"
            )
        )

        mock_settings = MagicMock()
        mock_settings.email.fallback_provider = "invalid"
        mocker.patch("apps.bot.email_service.app_settings", mock_settings)
        mocker.patch("apps.bot.email_service.get_email_provider", return_value=primary_provider)
        mocker.patch("apps.bot.email_service.get_email_fallback_provider", return_value=None)
        warning_spy = mocker.patch("apps.bot.email_service.logger.warning")

        send_transactional_email(
            subject="Test",
            message="body",
            recipient_list=["user@test.com"],
            event_type="transactional",
        )

        unavailable_calls = [
            c for c in warning_spy.call_args_list if c[0][0] == "email_fallback_provider_unavailable"
        ]
        assert len(unavailable_calls) == 1
        assert unavailable_calls[0][1]["reason"] == "config_error"

    def test_event_type_included_in_fallback_triggered_log(self, mocker):
        """event_type is included in email_fallback_triggered log event."""
        primary_provider = RecordingProvider(
            EmailSendResult(
                status="error", provider="resend", message_id=None, error_code="timeout"
            )
        )
        fallback_provider = RecordingProvider(
            EmailSendResult(status="sent", provider="smtp", message_id="msg-3", error_code=None)
        )

        mock_settings = MagicMock()
        mock_settings.email.fallback_provider = "smtp"
        mocker.patch("apps.bot.email_service.app_settings", mock_settings)
        mocker.patch("apps.bot.email_service.get_email_provider", return_value=primary_provider)
        mocker.patch(
            "apps.bot.email_service.get_email_fallback_provider", return_value=fallback_provider
        )
        info_spy = mocker.patch("apps.bot.email_service.logger.info")

        send_transactional_email(
            subject="Test",
            message="body",
            recipient_list=["user@test.com"],
            event_type="offline_alert",
        )

        triggered_calls = [
            c for c in info_spy.call_args_list if c[0][0] == "email_fallback_triggered"
        ]
        assert len(triggered_calls) == 1
        assert triggered_calls[0][1]["event_type"] == "offline_alert"


class TestFallbackIdempotencyKeyForwarding:
    """Tests for idempotency_key forwarding to fallback provider."""

    def test_idempotency_key_forwarded_to_fallback_provider(self, mocker):
        """idempotency_key is forwarded to the fallback provider send call."""
        primary_provider = RecordingProvider(
            EmailSendResult(
                status="error", provider="resend", message_id=None, error_code="api_error"
            )
        )
        fallback_provider = RecordingProvider(
            EmailSendResult(status="sent", provider="smtp", message_id="msg-fb", error_code=None)
        )

        mock_settings = MagicMock()
        mock_settings.email.fallback_provider = "smtp"
        mocker.patch("apps.bot.email_service.app_settings", mock_settings)
        mocker.patch("apps.bot.email_service.get_email_provider", return_value=primary_provider)
        mocker.patch(
            "apps.bot.email_service.get_email_fallback_provider", return_value=fallback_provider
        )

        send_transactional_email(
            subject="Test",
            message="body",
            recipient_list=["user@test.com"],
            idempotency_key="idem-key-123",
            event_type="email_confirmation",
        )

        assert len(fallback_provider.calls) == 1
        assert fallback_provider.calls[0]["idempotency_key"] == "idem-key-123"


class TestFallbackExceptionInSend:
    """Tests for fallback when fallback provider raises an exception in send()."""

    def test_fallback_provider_raises_exception_logs_fallback_failed(self, mocker):
        """When fallback provider raises during send, logs email_fallback_failed and returns error."""
        primary_provider = RecordingProvider(
            EmailSendResult(
                status="error", provider="resend", message_id=None, error_code="api_error"
            )
        )

        mock_settings = MagicMock()
        mock_settings.email.fallback_provider = "smtp"
        mocker.patch("apps.bot.email_service.app_settings", mock_settings)
        mocker.patch("apps.bot.email_service.get_email_provider", return_value=primary_provider)

        failing_fallback = FailingProvider(RuntimeError("SMTP connection timeout"))
        mocker.patch(
            "apps.bot.email_service.get_email_fallback_provider", return_value=failing_fallback
        )
        error_spy = mocker.patch("apps.bot.email_service.logger.error")

        result = send_transactional_email(
            subject="Test",
            message="body",
            recipient_list=["user@test.com"],
            event_type="transactional",
        )

        assert result["status"] == "error"
        assert result["provider"] == "smtp"
        assert result["error_code"] == "runtimeerror"

        failed_calls = [
            c for c in error_spy.call_args_list if c[0][0] == "email_fallback_failed"
        ]
        assert len(failed_calls) == 1
