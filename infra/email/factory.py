"""Factory para resolucao explicita do provider de email."""

import structlog
from django.core.mail import send_mail

from config.env import settings
from infra.email.protocols import EmailProvider, EmailSendResult

logger = structlog.get_logger(__name__)


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
        idempotency_key: str | None = None,
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
        except Exception as exc:
            # Extrai codigo de erro do boto3 ClientError (SES) sem vazar PII
            # Ex.: MessageRejected, MailFromDomainNotVerified, SendingPausedException
            error_code = "send_mail_failed"
            aws_code = (
                getattr(exc, "response", {}).get("Error", {}).get("Code")
                if hasattr(exc, "response")
                else None
            )
            if aws_code:
                error_code = f"ses_{aws_code}"
            logger.error(
                "django_send_mail_failed",
                provider=self._provider_name,
                exc_type=exc.__class__.__name__,
                aws_error_code=aws_code,
                from_email_domain=from_email.split("@", 1)[-1] if "@" in from_email else None,
                recipient_count=len(recipient_list),
            )
            return EmailSendResult(
                status="error",
                provider=self._provider_name,
                error_code=error_code,
            )


def _build_resend_provider() -> EmailProvider:
    resend_api_key = settings.email.resend_api_key
    if not resend_api_key:
        raise EmailProviderConfigurationError("RESEND_API_KEY ausente para provider resend")

    try:
        from infra.email.providers.resend_provider import ResendEmailProvider
    except ModuleNotFoundError as exc:
        raise EmailProviderConfigurationError("Dependencia resend nao instalada") from exc

    return ResendEmailProvider(api_key=resend_api_key)


def _build_brevo_provider() -> EmailProvider:
    brevo_api_key = settings.email.brevo_api_key
    if not brevo_api_key:
        raise EmailProviderConfigurationError("BREVO_API_KEY ausente para provider brevo")

    try:
        from infra.email.providers.brevo_provider import BrevoEmailProvider
    except ModuleNotFoundError as exc:
        raise EmailProviderConfigurationError("Dependencia brevo nao instalada") from exc

    return BrevoEmailProvider(api_key=brevo_api_key)


def get_email_provider(provider_name: str | None = None) -> EmailProvider:
    """Resolve provider exclusivamente por EMAIL_PROVIDER, sem fallback implicito."""
    resolved_provider = (provider_name or settings.email.provider).strip().lower()

    if resolved_provider == "resend":
        return _build_resend_provider()

    if resolved_provider == "brevo":
        return _build_brevo_provider()

    if resolved_provider in {"ses", "smtp", "console"}:
        return DjangoSendMailProvider(provider_name=resolved_provider)

    raise UnknownEmailProviderError(
        f"Provider de email desconhecido: {resolved_provider!r}. "
        "Configure EMAIL_PROVIDER com um valor valido."
    )


def get_email_fallback_provider() -> EmailProvider | None:
    """Resolve fallback provider se EMAIL_FALLBACK_PROVIDER estiver configurado.

    Returns the fallback provider instance, or None if:
    - EMAIL_FALLBACK_PROVIDER is not configured (empty string)
    - The fallback provider name is unknown or misconfigured (graceful degradation)
    """
    fallback_name = settings.email.fallback_provider
    if not fallback_name:
        return None

    try:
        return get_email_provider(fallback_name)
    except (UnknownEmailProviderError, EmailProviderConfigurationError) as exc:
        logger.warning(
            "email_fallback_provider_config_error",
            fallback_provider=fallback_name,
            error=str(exc),
        )
        return None
