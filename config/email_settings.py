from dataclasses import dataclass

import structlog

from config._helpers import _get_secret_or_env, env

_logger = structlog.get_logger(__name__)

_KNOWN_PROVIDERS = {"resend", "ses", "smtp", "console"}


@dataclass
class EmailSettings:
    provider: str
    backend: str
    host: str
    port: int
    use_tls: bool
    user: str
    password: str
    from_email: str
    resend_api_key: str
    fallback_provider: str

    def __init__(self) -> None:
        """Initialize from environment — overrides dataclass __init__ to read env vars."""
        self.provider = env("EMAIL_PROVIDER")
        self.backend = env("EMAIL_BACKEND")
        self.host = env("EMAIL_HOST")
        self.port = env("EMAIL_PORT")
        self.use_tls = env("EMAIL_USE_TLS")
        self.user = env("EMAIL_HOST_USER")
        self.password = _get_secret_or_env("email_password", "EMAIL_HOST_PASSWORD", "")
        self.from_email = env("DEFAULT_FROM_EMAIL")
        self.resend_api_key = _get_secret_or_env("resend_api_key", "RESEND_API_KEY", "")
        self.fallback_provider = env("EMAIL_FALLBACK_PROVIDER")
        # WR-01: validate fallback provider at startup so misconfigs surface early
        if (
            self.fallback_provider
            and self.fallback_provider.strip().lower() not in _KNOWN_PROVIDERS
        ):
            _logger.warning(
                "email_fallback_provider_unknown",
                fallback_provider=self.fallback_provider,
                known_providers=sorted(_KNOWN_PROVIDERS),
            )
