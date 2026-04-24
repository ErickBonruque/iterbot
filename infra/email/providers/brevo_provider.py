"""Adapter HTTP da API Brevo (antiga Sendinblue) para envio transacional.

Docs: https://developers.brevo.com/reference/sendtransacemail
"""

from __future__ import annotations

import requests

from infra.email.protocols import EmailSendResult

BREVO_API_URL = "https://api.brevo.com/v3/smtp/email"
DEFAULT_TIMEOUT_SECONDS = 10


class BrevoEmailProvider:
    """Envia e-mails transacionais via API REST do Brevo.

    Requer que o `from_email` esteja cadastrado como *verified sender* no
    dashboard do Brevo (Senders, Domains & Dedicated IPs > Senders). No plano
    gratuito o limite é 300 e-mails/dia e qualquer destinatário é aceito desde
    que o remetente esteja verificado.
    """

    provider_name = "brevo"

    def __init__(self, api_key: str, timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS) -> None:
        self._api_key = api_key
        self._timeout = timeout_seconds

    def send(
        self,
        *,
        subject: str,
        message: str,
        from_email: str,
        recipient_list: list[str],
        idempotency_key: str | None = None,
    ) -> EmailSendResult:
        payload: dict = {
            "sender": {"email": from_email},
            "to": [{"email": addr} for addr in recipient_list],
            "subject": subject,
            "textContent": message,
        }
        headers = {
            "api-key": self._api_key,
            "accept": "application/json",
            "content-type": "application/json",
        }
        if idempotency_key:
            # Brevo não suporta Idempotency-Key nativamente; envia como header
            # custom para rastreio — ignorado pelo servidor mas útil em proxies.
            headers["Idempotency-Key"] = idempotency_key

        try:
            response = requests.post(
                BREVO_API_URL,
                json=payload,
                headers=headers,
                timeout=self._timeout,
            )
        except requests.exceptions.Timeout:
            return EmailSendResult(
                status="error",
                provider=self.provider_name,
                message_id=None,
                error_code="timeout",
            )
        except requests.exceptions.RequestException as exc:
            return EmailSendResult(
                status="error",
                provider=self.provider_name,
                message_id=None,
                error_code=exc.__class__.__name__.lower(),
            )

        if response.status_code in (200, 201):
            try:
                data = response.json()
            except ValueError:
                data = {}
            message_id = data.get("messageId") if isinstance(data, dict) else None
            return EmailSendResult(
                status="sent",
                provider=self.provider_name,
                message_id=message_id,
                error_code=None,
            )

        # Falha: extrai código estruturado da API (ver docs Brevo)
        error_code = f"http_{response.status_code}"
        try:
            body = response.json()
            if isinstance(body, dict) and body.get("code"):
                error_code = f"brevo_{body['code']}"
        except ValueError:
            pass
        return EmailSendResult(
            status="error",
            provider=self.provider_name,
            message_id=None,
            error_code=error_code,
        )
