"""Health check module for email provider connectivity and configuration."""

import socket

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
        provider_name: The email provider name (e.g. 'resend', 'smtp', 'ses', 'console').
        api_key: Optional API key for providers that need one (e.g. Resend).

    Returns:
        Dict with 'status', 'provider', and optionally 'error' or 'note' keys.
    """
    resolved = provider_name.strip().lower()

    if resolved == "resend":
        return _check_resend_health(api_key)
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
    except (socket.timeout, OSError, ConnectionError) as exc:
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
        api_key = email_settings.resend_api_key

        primary = check_email_provider_health(provider_name, api_key=api_key)

        fallback_provider = getattr(email_settings, "fallback_provider", "")
        if fallback_provider:
            fallback_api_key = None
            if fallback_provider == "resend":
                fallback_api_key = email_settings.resend_api_key
            fallback = check_email_provider_health(fallback_provider, api_key=fallback_api_key)
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
