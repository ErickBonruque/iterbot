"""Testes do adapter Brevo (infra/email/providers/brevo_provider)."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from infra.email.protocols import EmailSendResult
from infra.email.providers.brevo_provider import (
    BREVO_API_URL,
    BrevoEmailProvider,
)


def _fake_response(*, status_code: int, body: dict | None = None) -> SimpleNamespace:
    def _json() -> dict:
        if body is None:
            raise ValueError("no body")
        return body

    return SimpleNamespace(status_code=status_code, json=_json)


def test_brevo_provider_envia_payload_correto(mocker):
    fake_response = _fake_response(status_code=201, body={"messageId": "brevo-msg-1"})
    post_spy = mocker.patch(
        "infra.email.providers.brevo_provider.requests.post",
        return_value=fake_response,
    )

    provider = BrevoEmailProvider(api_key="xkeysib-fake-key")
    result = provider.send(
        subject="Assunto",
        message="Corpo da mensagem",
        from_email="no-reply@example.com",
        recipient_list=["aluno@example.com"],
        idempotency_key="idem-1",
    )

    assert result == EmailSendResult(
        status="sent",
        provider="brevo",
        message_id="brevo-msg-1",
        error_code=None,
    )

    post_spy.assert_called_once()
    call_kwargs = post_spy.call_args
    assert call_kwargs.args[0] == BREVO_API_URL
    assert call_kwargs.kwargs["json"] == {
        "sender": {"email": "no-reply@example.com"},
        "to": [{"email": "aluno@example.com"}],
        "subject": "Assunto",
        "textContent": "Corpo da mensagem",
    }
    assert call_kwargs.kwargs["headers"]["api-key"] == "xkeysib-fake-key"
    assert call_kwargs.kwargs["headers"]["Idempotency-Key"] == "idem-1"


@pytest.mark.parametrize(
    "status_code, body, expected_code",
    [
        (400, {"code": "invalid_parameter", "message": "bad"}, "brevo_invalid_parameter"),
        (401, {"code": "unauthorized"}, "brevo_unauthorized"),
        (500, None, "http_500"),
    ],
)
def test_brevo_provider_traduz_erros_api(mocker, status_code, body, expected_code):
    mocker.patch(
        "infra.email.providers.brevo_provider.requests.post",
        return_value=_fake_response(status_code=status_code, body=body),
    )

    provider = BrevoEmailProvider(api_key="xkeysib-fake-key")
    result = provider.send(
        subject="s",
        message="m",
        from_email="from@example.com",
        recipient_list=["to@example.com"],
    )

    assert result.status == "error"
    assert result.provider == "brevo"
    assert result.error_code == expected_code


def test_brevo_provider_trata_timeout(mocker):
    import requests

    mocker.patch(
        "infra.email.providers.brevo_provider.requests.post",
        side_effect=requests.exceptions.Timeout(),
    )

    provider = BrevoEmailProvider(api_key="xkeysib-fake-key")
    result = provider.send(
        subject="s",
        message="m",
        from_email="from@example.com",
        recipient_list=["to@example.com"],
    )

    assert result == EmailSendResult(
        status="error",
        provider="brevo",
        message_id=None,
        error_code="timeout",
    )
