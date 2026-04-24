"""Health check module for email provider connectivity and configuration."""

import socket

import requests
import structlog

logger = structlog.get_logger(__name__)


def _get_email_settings():
    """Get email settings from config.env (injectable for testing)."""
    from config.env import settings as app_config

    return app_config.email


def check_email_provider_health(
    provider_name: str,
    api_key: str | None = None,
) -> dict[str, str]:
    """Check health of a specific email provider.

    Args:
        provider_name: The email provider name (e.g. 'resend', 'brevo', 'smtp', 'ses', 'console').
        api_key: Optional API key for providers that need one (e.g. Resend, Brevo).

    Returns:
        Dict with 'status', 'provider', and optionally 'error' or 'note' keys.
    """
    resolved = provider_name.strip().lower()

    if resolved == "resend":
        return _check_resend_health(api_key)
    if resolved == "brevo":
        return _check_brevo_health(api_key)
    if resolved in {"smtp", "ses"}:
        return _check_smtp_health()
    if resolved == "console":
        return {
            "status": "healthy",
            "provider": "console",
            "note": "console provider - no external connectivity",
        }

    return {
        "status": "unhealthy",
        "provider": provider_name,
        "error": "unknown provider",
    }


def _check_resend_health(api_key: str | None) -> dict[str, str]:
    """Verify Resend API connectivity and key validity."""
    if not api_key:
        return {
            "status": "unhealthy",
            "provider": "resend",
            "error": "API key not configured",
        }

    try:
        import resend as _resend

        _resend.api_key = api_key
        # Lightweight API call to verify connectivity + key validity
        _resend.Domains.list()
        return {"status": "healthy", "provider": "resend"}
    except Exception as exc:
        error_msg = f"{type(exc).__name__}: API connectivity check failed"  # T-42-01: never expose raw exception (may contain API key)
        return {
            "status": "unhealthy",
            "provider": "resend",
            "error": error_msg,
        }


def _check_brevo_health(api_key: str | None) -> dict[str, str]:
    """Verifica conectividade com API Brevo e validade da chave via /v3/account.

    Endpoint leve (GET) que valida tanto a chave quanto a conexao sem enviar
    e-mail. Qualquer 2xx = healthy; 401/403 = chave invalida; outros = unhealthy.
    """
    if not api_key:
        return {
            "status": "unhealthy",
            "provider": "brevo",
            "error": "API key not configured",
        }

    try:
        response = requests.get(
            "https://api.brevo.com/v3/account",
            headers={"api-key": api_key, "accept": "application/json"},
            timeout=5,
        )
        if 200 <= response.status_code < 300:
            return {"status": "healthy", "provider": "brevo"}
        return {
            "status": "unhealthy",
            "provider": "brevo",
            "error": f"http_{response.status_code}",
        }
    except Exception as exc:
        # T-42-01: nao expor excecao crua (pode conter a chave)
        return {
            "status": "unhealthy",
            "provider": "brevo",
            "error": f"{type(exc).__name__}: API connectivity check failed",
        }


def _check_smtp_health() -> dict[str, str]:
    """Verify SMTP/SES connectivity via TCP connection to configured host:port."""
    from django.conf import settings as django_settings

    host = getattr(django_settings, "EMAIL_HOST", "")
    port = getattr(django_settings, "EMAIL_PORT", 587)

    if not host:
        return {
            "status": "unhealthy",
            "provider": "smtp",
            "error": "EMAIL_HOST not configured",
        }

    try:
        with socket.create_connection((host, port), timeout=5):
            return {"status": "healthy", "provider": "smtp"}
    except (TimeoutError, OSError, ConnectionError) as exc:
        key_status = (
            "configured" if getattr(django_settings, "EMAIL_HOST_USER", "") else "not_configured"
        )
        return {
            "status": "unhealthy",
            "provider": "smtp",
            "error": f"connection failed: {type(exc).__name__}",
            "key_status": key_status,
        }


def check_email_health() -> dict:
    """Check health of the configured email provider(s).

    Returns a dict with an 'email' key containing primary provider status
    and optionally fallback provider status if EMAIL_FALLBACK_PROVIDER is set.
    """
    try:
        email_settings = _get_email_settings()
        provider_name = email_settings.provider

        def _api_key_for(name: str) -> str | None:
            resolved = name.strip().lower()
            if resolved == "resend":
                return email_settings.resend_api_key
            if resolved == "brevo":
                return getattr(email_settings, "brevo_api_key", "")
            return None

        primary = check_email_provider_health(provider_name, api_key=_api_key_for(provider_name))

        fallback_provider = getattr(email_settings, "fallback_provider", "")
        if fallback_provider:
            fallback = check_email_provider_health(
                fallback_provider, api_key=_api_key_for(fallback_provider)
            )
            return {"email": {"primary": primary, "fallback": fallback}}

        return {"email": primary}
    except Exception as exc:
        logger.error("email_health_check_failed", error=type(exc).__name__, exc_info=True)
        return {
            "email": {
                "status": "unhealthy",
                "error": f"{type(exc).__name__}: health check failed",  # T-42-01: no raw exception in response
            }
        }
