from apps.bot.email_service import send_confirmation_email_to_user, send_offline_alert_email
from infra.email.idempotency import build_email_idempotency_key
from apps.users.models import UserProfile
from infra.email.protocols import EmailSendResult


class RecordingProvider:
    def __init__(self, result: EmailSendResult) -> None:
        self._result = result
        self.calls: list[dict[str, object]] = []

    def send(self, **kwargs) -> EmailSendResult:
        self.calls.append(kwargs)
        return self._result


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
