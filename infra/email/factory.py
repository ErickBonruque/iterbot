"""Factory para resolucao explicita do provider de email."""

from django.core.mail import send_mail

from config.env import settings
from infra.email.protocols import EmailProvider, EmailSendResult


class UnknownEmailProviderError(ValueError):
    """Erro para provider desconhecido configurado em EMAIL_PROVIDER."""


class EmailProviderConfigurationError(RuntimeError):
    """Erro de configuracao do provider de email."""


class DjangoSendMailProvider:
    """Adapter para providers legados baseados em backend Django."""

    def __init__(self, provider_name: str) -> None:
        self._provider_name = provider_name

    def send(
        self,
        *,
        subject: str,
        message: str,
        from_email: str,
        recipient_list: list[str],
    ) -> EmailSendResult:
        try:
            send_mail(
                subject=subject,
                message=message,
                from_email=from_email,
                recipient_list=recipient_list,
                fail_silently=False,
            )
            return EmailSendResult(status="sent", provider=self._provider_name)
        except Exception:
            return EmailSendResult(
                status="error",
                provider=self._provider_name,
                error_code="send_mail_failed",
            )


def _build_resend_provider() -> EmailProvider:
    resend_api_key = settings.email.resend_api_key
    if not resend_api_key:
        raise EmailProviderConfigurationError("RESEND_API_KEY ausente para provider resend")

    from infra.email.providers.resend_provider import ResendEmailProvider

    return ResendEmailProvider(api_key=resend_api_key)


def get_email_provider(provider_name: str | None = None) -> EmailProvider:
    """Resolve provider exclusivamente por EMAIL_PROVIDER, sem fallback implicito."""
    resolved_provider = (provider_name or settings.email.provider).strip().lower()

    if resolved_provider == "resend":
        return _build_resend_provider()

    if resolved_provider in {"ses", "smtp", "console"}:
        return DjangoSendMailProvider(provider_name=resolved_provider)

    raise UnknownEmailProviderError(
        f"Provider de email desconhecido: {resolved_provider!r}. "
        "Configure EMAIL_PROVIDER com um valor valido."
    )
