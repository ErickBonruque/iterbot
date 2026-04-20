from infra.email.factory import DjangoSendMailProvider
from infra.email.idempotency import build_email_idempotency_key
from infra.email.protocols import EmailSendResult


def test_build_email_idempotency_key_is_deterministic_and_normalized():
    first_key = build_email_idempotency_key(
        "password_reset",
        recipient="Aluno@UTFPR.edu.br ",
        event_token=" token-123 ",
        event_uid=" 42 ",
    )
    second_key = build_email_idempotency_key(
        "password_reset",
        recipient="aluno@utfpr.edu.br",
        event_token="token-123",
        event_uid="42",
    )

    assert first_key == second_key
    assert first_key.startswith("email:password_reset:")


def test_build_email_idempotency_key_changes_for_different_inputs():
    base_key = build_email_idempotency_key(
        "password_reset",
        recipient="aluno@utfpr.edu.br",
        event_token="token-123",
    )
    different_token_key = build_email_idempotency_key(
        "password_reset",
        recipient="aluno@utfpr.edu.br",
        event_token="token-456",
    )
    different_event_key = build_email_idempotency_key(
        "email_confirmation",
        recipient="aluno@utfpr.edu.br",
        event_token="token-123",
    )

    assert base_key != different_token_key
    assert base_key != different_event_key


def test_legacy_django_provider_accepts_idempotency_key(mocker):
    send_mail_spy = mocker.patch("infra.email.factory.send_mail", return_value=1)
    provider = DjangoSendMailProvider(provider_name="smtp")

    result = provider.send(
        subject="Assunto",
        message="Mensagem",
        from_email="no-reply@example.com",
        recipient_list=["aluno@example.com"],
        idempotency_key="idempotency-key-123",
    )

    assert result == EmailSendResult(status="sent", provider="smtp")
    send_mail_spy.assert_called_once_with(
        subject="Assunto",
        message="Mensagem",
        from_email="no-reply@example.com",
        recipient_list=["aluno@example.com"],
        fail_silently=False,
    )


def test_resend_provider_forwards_idempotency_headers(mocker):
    from types import SimpleNamespace

    send_spy = mocker.Mock(return_value={"id": "msg-123"})
    fake_resend = SimpleNamespace(api_key=None, Emails=SimpleNamespace(send=send_spy))
    mocker.patch.dict("sys.modules", {"resend": fake_resend})

    from infra.email.providers.resend_provider import ResendEmailProvider

    provider = ResendEmailProvider(api_key="test-api-key")
    result = provider.send(
        subject="Assunto",
        message="Mensagem",
        from_email="no-reply@example.com",
        recipient_list=["aluno@example.com"],
        idempotency_key="idempotency-key-123",
    )

    assert result == EmailSendResult(
        status="sent",
        provider="resend",
        message_id="msg-123",
        error_code=None,
    )
    send_spy.assert_called_once_with(
        {
            "from": "no-reply@example.com",
            "to": ["aluno@example.com"],
            "subject": "Assunto",
            "text": "Mensagem",
            "headers": {"Idempotency-Key": "idempotency-key-123"},
        }
    )
