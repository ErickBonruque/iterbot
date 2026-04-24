from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent

# Initialize django-environ
env = environ.Env(
    DEBUG=(bool, False),
    DJANGO_SECRET_KEY=(str, ""),
    ALLOWED_HOSTS=(str, "*"),
    DATABASE_URL=(str, ""),
    REDIS_URL=(str, "redis://redis:6379/0"),
    WAHA_URL=(str, "http://waha:3000"),
    WAHA_API_KEY=(str, ""),
    WAHA_SESSION_NAME=(str, "default"),
    WAHA_TIMEOUT_SECONDS=(int, 5),
    BOT_DASHBOARD_USERNAME=(str, "admin"),
    BOT_DASHBOARD_PASSWORD=(str, "password"),
    DJANGO_ADMIN_USERNAME=(str, "admin"),
    DJANGO_ADMIN_PASSWORD=(str, "admin"),
    DOMAIN=(str, "localhost"),
    PORTAL_BASE_URL=(str, ""),
    EMAIL_BACKEND=(str, "django.core.mail.backends.console.EmailBackend"),
    EMAIL_HOST=(str, ""),
    EMAIL_PORT=(int, 587),
    EMAIL_USE_TLS=(bool, True),
    EMAIL_HOST_USER=(str, ""),
    EMAIL_HOST_PASSWORD=(str, ""),
    DEFAULT_FROM_EMAIL=(str, "noreply@iterbot.example.com"),
    EMAIL_PROVIDER=(str, "console"),
    EMAIL_FALLBACK_PROVIDER=(str, ""),
    RESEND_API_KEY=(str, ""),
    BREVO_API_KEY=(str, ""),
    AWS_ACCESS_KEY_ID=(str, ""),
    AWS_SECRET_ACCESS_KEY=(str, ""),
    AWS_DEFAULT_REGION=(str, "us-east-1"),
    WAHA_DASHBOARD_USERNAME=(str, "admin"),
    WAHA_DASHBOARD_PASSWORD=(str, "password"),
    WHATSAPP_SWAGGER_USERNAME=(str, "swagger"),
    WHATSAPP_SWAGGER_PASSWORD=(str, "password"),
)

# Read .env file if it exists
env_file = BASE_DIR / ".env"
if env_file.exists():
    environ.Env.read_env(str(env_file))


def _read_secret_file(secret_name: str) -> str | None:
    """Read secret from Docker secrets file."""
    secret_path = Path(f"/run/secrets/{secret_name}")
    if secret_path.exists():
        return secret_path.read_text().strip()
    return None


def _get_secret_or_env(secret_name: str, env_var: str, default: str = "") -> str:
    """Get value from Docker secret file first, then environment variable, then default."""
    secret_value = _read_secret_file(secret_name)
    if secret_value:
        return secret_value
    return env(env_var, default=default)
