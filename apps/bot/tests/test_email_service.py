from apps.bot.email_service import send_confirmation_email_to_user, send_offline_alert_email
from apps.users.models import UserProfile
from infra.email.protocols import EmailSendResult


class DummyProvider:
    def __init__(self, result: EmailSendResult) -> None:
        self._result = result

    def send(self, **_kwargs) -> EmailSendResult:
        return self._result


def test_send_confirmation_email_to_user_returns_sent_with_provider_payload(db, mocker):
    user = UserProfile.objects.create(
        phone_number="554199999999@c.us",
        email="aluno@alunos.utfpr.edu.br",
        ra="123456",
        email_verified=False,
        email_confirmation_token="token-123",
    )
    provider = DummyProvider(
        EmailSendResult(status="sent", provider="resend", message_id="msg-1", error_code=None)
    )
    mocker.patch("apps.bot.email_service.get_email_provider", return_value=provider)

    result = send_confirmation_email_to_user(user.id)

    assert result["status"] == "sent"
    assert result["provider"] == "resend"
    assert result["message_id"] == "msg-1"


def test_send_confirmation_email_to_user_returns_provider_error(db, mocker):
    user = UserProfile.objects.create(
        phone_number="554188888888@c.us",
        email="aluno2@alunos.utfpr.edu.br",
        ra="654321",
        email_verified=False,
        email_confirmation_token="token-456",
    )
    provider = DummyProvider(
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
    provider = DummyProvider(
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
