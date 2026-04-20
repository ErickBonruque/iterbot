"""Adapter do SDK Resend para o contrato de provider de email."""

import resend

from infra.email.protocols import EmailSendResult


class ResendEmailProvider:
    """Implementa envio transacional usando SDK oficial Resend."""

    provider_name = "resend"

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key

    def send(
        self,
        *,
        subject: str,
        message: str,
        from_email: str,
        recipient_list: list[str],
        idempotency_key: str | None = None,
    ) -> EmailSendResult:
        try:
            resend.api_key = self._api_key
            payload = {
                "from": from_email,
                "to": recipient_list,
                "subject": subject,
                "text": message,
            }
            if idempotency_key:
                payload["headers"] = {"Idempotency-Key": idempotency_key}
            response = resend.Emails.send(payload)
            message_id = response.get("id") if isinstance(response, dict) else None
            return EmailSendResult(
                status="sent",
                provider=self.provider_name,
                message_id=message_id,
                error_code=None,
            )
        except Exception as exc:
            return EmailSendResult(
                status="error",
                provider=self.provider_name,
                message_id=None,
                error_code=exc.__class__.__name__.lower(),
            )
