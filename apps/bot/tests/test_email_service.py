from unittest.mock import MagicMock

from apps.bot.email_service import (
    mask_recipient,
    send_confirmation_email_to_user,
    send_offline_alert_email,
    send_transactional_email,
)
from apps.users.models import UserProfile
from infra.email.factory import (
    EmailProviderConfigurationError,
    UnknownEmailProviderError,
)
from infra.email.idempotency import build_email_idempotency_key
from infra.email.protocols import EmailSendResult


class RecordingProvider:
    def __init__(self, result: EmailSendResult) -> None:
        self._result = result
        self.calls: list[dict[str, object]] = []

    def send(self, **kwargs) -> EmailSendResult:
        self.calls.append(kwargs)
        return self._result


# --- mask_recipient tests ---


def test_mask_recipient_normal_email():
    assert mask_recipient("joao@alunos.utfpr.edu.br") == "j***@alunos.utfpr.edu.br"


def test_mask_recipient_short_local_part():
    assert mask_recipient("a@b.co") == "a***@b.co"


def test_mask_recipient_no_at_sign():
    assert mask_recipient("not_an_email") == "***"


def test_mask_recipient_empty_local():
    assert mask_recipient("@domain.com") == "***@domain.com"


# --- Structured logging tests ---


def test_send_transactional_email_logs_success(mocker):
    provider = RecordingProvider(
        EmailSendResult(status="sent", provider="resend", message_id="msg-1", error_code=None)
    )
    mocker.patch("apps.bot.email_service.get_email_provider", return_value=provider)
    info_spy = mocker.patch("apps.bot.email_service.logger.info")

    result = send_transactional_email(
        subject="Test",
        message="body",
        recipient_list=["joao@alunos.utfpr.edu.br"],
        event_type="email_confirmation",
    )

    assert result["status"] == "sent"
    info_spy.assert_called_once()
    call_kwargs = info_spy.call_args[1]
    assert call_kwargs["provider"] == "resend"
    assert call_kwargs["status"] == "sent"
    assert call_kwargs["message_id"] == "msg-1"
    assert call_kwargs["event_type"] == "email_confirmation"
    assert "duration_ms" in call_kwargs
    assert call_kwargs["recipient"] == "j***@alunos.utfpr.edu.br"


def test_send_transactional_email_logs_failure(mocker):
    provider = RecordingProvider(
        EmailSendResult(
            status="error",
            provider="resend",
            message_id=None,
            error_code="api_error",
        )
    )
    mocker.patch("apps.bot.email_service.get_email_provider", return_value=provider)
    error_spy = mocker.patch("apps.bot.email_service.logger.error")

    result = send_transactional_email(
        subject="Test",
        message="body",
        recipient_list=["joao@alunos.utfpr.edu.br"],
        event_type="offline_alert",
    )

    assert result["status"] == "error"
    # Find the email_send_failure call (there should be exactly one)
    failure_calls = [c for c in error_spy.call_args_list if c[0][0] == "email_send_failure"]
    assert len(failure_calls) == 1
    call_kwargs = failure_calls[0][1]
    assert call_kwargs["provider"] == "resend"
    assert call_kwargs["error_code"] == "api_error"
    assert call_kwargs["event_type"] == "offline_alert"
    assert "duration_ms" in call_kwargs


def test_send_transactional_email_logs_unknown_provider_error(mocker):
    mocker.patch(
        "apps.bot.email_service.get_email_provider",
        side_effect=UnknownEmailProviderError("bad provider"),
    )
    error_spy = mocker.patch("apps.bot.email_service.logger.error")

    result = send_transactional_email(
        subject="Test",
        message="body",
        recipient_list=["test@test.com"],
        event_type="transactional",
    )

    assert result["status"] == "error"
    unknown_calls = [c for c in error_spy.call_args_list if c[0][0] == "email_provider_unknown"]
    assert len(unknown_calls) == 1
    assert unknown_calls[0][1]["event_type"] == "transactional"


def test_send_transactional_email_logs_configuration_error(mocker):
    mocker.patch(
        "apps.bot.email_service.get_email_provider",
        side_effect=EmailProviderConfigurationError("misconfigured"),
    )
    error_spy = mocker.patch("apps.bot.email_service.logger.error")

    result = send_transactional_email(
        subject="Test",
        message="body",
        recipient_list=["test@test.com"],
        event_type="email_confirmation",
    )

    assert result["status"] == "error"
    config_calls = [
        c for c in error_spy.call_args_list if c[0][0] == "email_provider_configuration_error"
    ]
    assert len(config_calls) == 1
    assert config_calls[0][1]["event_type"] == "email_confirmation"


def test_send_transactional_email_logs_generic_exception(mocker):
    mocker.patch(
        "apps.bot.email_service.get_email_provider",
        side_effect=RuntimeError("unexpected"),
    )
    error_spy = mocker.patch("apps.bot.email_service.logger.error")

    result = send_transactional_email(
        subject="Test",
        message="body",
        recipient_list=["test@test.com"],
        event_type="offline_alert",
    )

    assert result["status"] == "error"
    failed_calls = [c for c in error_spy.call_args_list if c[0][0] == "email_provider_send_failed"]
    assert len(failed_calls) == 1
    assert failed_calls[0][1]["event_type"] == "offline_alert"


# --- event_type passthrough tests ---


def test_send_confirmation_email_to_user_passes_event_type(db, mocker):
    user = UserProfile.objects.create(
        phone_number="554199999999@c.us",
        email="aluno@alunos.utfpr.edu.br",
        ra="123456",
        email_verified=False,
        email_confirmation_token="token-123",
    )
    provider = RecordingProvider(
        EmailSendResult(status="sent", provider="resend", message_id="msg-1", error_code=None)
    )
    mocker.patch("apps.bot.email_service.get_email_provider", return_value=provider)
    info_spy = mocker.patch("apps.bot.email_service.logger.info")

    result = send_confirmation_email_to_user(user.id)

    assert result["status"] == "sent"
    # Verify that the structured log was called with event_type=email_confirmation
    call_kwargs = info_spy.call_args[1]
    assert call_kwargs["event_type"] == "email_confirmation"


def test_send_offline_alert_email_passes_event_type(mocker):
    provider = RecordingProvider(
        EmailSendResult(status="sent", provider="resend", message_id="msg-2", error_code=None)
    )
    mocker.patch("apps.bot.email_service.get_email_provider", return_value=provider)
    info_spy = mocker.patch("apps.bot.email_service.logger.info")

    send_offline_alert_email(session_name="default", current_status="offline")

    call_kwargs = info_spy.call_args[1]
    assert call_kwargs["event_type"] == "offline_alert"


# --- Original existing tests (preserved) ---


def test_send_confirmation_email_to_user_returns_sent_with_provider_payload(db, mocker):
    user = UserProfile.objects.create(
        phone_number="554199999999@c.us",
        email="aluno@alunos.utfpr.edu.br",
        ra="123456",
        email_verified=False,
        email_confirmation_token="token-123",
    )
    provider = RecordingProvider(
        EmailSendResult(status="sent", provider="resend", message_id="msg-1", error_code=None)
    )
    mocker.patch("apps.bot.email_service.get_email_provider", return_value=provider)

    result = send_confirmation_email_to_user(user.id)

    assert result["status"] == "sent"
    assert result["provider"] == "resend"
    assert result["message_id"] == "msg-1"
    assert len(provider.calls) == 1
    assert provider.calls[0]["idempotency_key"] == build_email_idempotency_key(
        "email_confirmation",
        recipient=user.email,
        event_token=user.email_confirmation_token,
        event_uid=str(user.id),
    )


def test_send_confirmation_email_to_user_reuses_idempotency_key_on_retry(db, mocker):
    user = UserProfile.objects.create(
        phone_number="554188888888@c.us",
        email="aluno2@alunos.utfpr.edu.br",
        ra="654321",
        email_verified=False,
        email_confirmation_token="token-456",
    )
    provider = RecordingProvider(
        EmailSendResult(status="sent", provider="resend", message_id="msg-2", error_code=None)
    )
    mocker.patch("apps.bot.email_service.get_email_provider", return_value=provider)

    send_confirmation_email_to_user(user.id)
    send_confirmation_email_to_user(user.id)

    first_call, second_call = provider.calls
    assert first_call["idempotency_key"] == second_call["idempotency_key"]


def test_send_confirmation_email_to_user_returns_provider_error(db, mocker):
    user = UserProfile.objects.create(
        phone_number="554177777777@c.us",
        email="aluno3@alunos.utfpr.edu.br",
        ra="654322",
        email_verified=False,
        email_confirmation_token="token-789",
    )
    provider = RecordingProvider(
        EmailSendResult(
            status="error",
            provider="resend",
            message_id=None,
            error_code="api_error",
        )
    )
    mocker.patch("apps.bot.email_service.get_email_provider", return_value=provider)

    result = send_confirmation_email_to_user(user.id)

    assert result["status"] == "error"
    assert result["reason"] == "provider_error"
    assert result["error_code"] == "api_error"


def test_send_confirmation_email_to_user_user_not_found(db):
    result = send_confirmation_email_to_user(99999)

    assert result["status"] == "error"
    assert result["reason"] == "user_not_found"


def test_send_offline_alert_email_logs_warning_on_provider_failure(mocker):
    provider = RecordingProvider(
        EmailSendResult(
            status="error",
            provider="resend",
            message_id=None,
            error_code="timeout",
        )
    )
    mocker.patch("apps.bot.email_service.get_email_provider", return_value=provider)
    warning_spy = mocker.patch("apps.bot.email_service.logger.warning")

    send_offline_alert_email(session_name="default", current_status="offline")

    warning_spy.assert_called_once()


# --- Integration-level fallback tests ---


class TestSendConfirmationEmailFallbackIntegration:
    """Integration tests for send_confirmation_email_to_user with fallback."""

    def test_confirmation_email_works_end_to_end_primary_succeeds(self, db, mocker):
        """send_confirmation_email_to_user works end-to-end when primary succeeds (no fallback)."""
        user = UserProfile.objects.create(
            phone_number="554199999998@c.us",
            email="aluno_fb@alunos.utfpr.edu.br",
            ra="112233",
            email_verified=False,
            email_confirmation_token="token-fb-1",
        )
        provider = RecordingProvider(
            EmailSendResult(status="sent", provider="resend", message_id="msg-1", error_code=None)
        )
        mock_settings = MagicMock()
        mock_settings.email.fallback_provider = ""
        mocker.patch("apps.bot.email_service.app_settings", mock_settings)
        mocker.patch("apps.bot.email_service.get_email_provider", return_value=provider)

        result = send_confirmation_email_to_user(user.id)

        assert result["status"] == "sent"
        assert result["provider"] == "resend"

    def test_confirmation_email_falls_back_on_primary_failure(self, db, mocker):
        """send_confirmation_email_to_user falls back when primary fails and fallback configured."""
        user = UserProfile.objects.create(
            phone_number="554199999997@c.us",
            email="aluno_fb2@alunos.utfpr.edu.br",
            ra="445566",
            email_verified=False,
            email_confirmation_token="token-fb-2",
        )
        primary_provider = RecordingProvider(
            EmailSendResult(
                status="error", provider="resend", message_id=None, error_code="api_error"
            )
        )
        fallback_provider = RecordingProvider(
            EmailSendResult(
                status="sent", provider="smtp", message_id="msg-fb-1", error_code=None
            )
        )

        mock_settings = MagicMock()
        mock_settings.email.fallback_provider = "smtp"
        mocker.patch("apps.bot.email_service.app_settings", mock_settings)
        mocker.patch("apps.bot.email_service.get_email_provider", return_value=primary_provider)
        mocker.patch(
            "apps.bot.email_service.get_email_fallback_provider",
            return_value=fallback_provider,
        )

        result = send_confirmation_email_to_user(user.id)

        assert result["status"] == "sent"
        # fallback sends the email successfully
        assert result["provider"] == "smtp"
