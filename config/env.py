import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

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
)

# Read .env file if it exists
env_file = BASE_DIR / ".env"
if env_file.exists():
    environ.Env.read_env(str(env_file))


def _read_secret_file(secret_name: str) -> Optional[str]:
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


@dataclass
class DjangoSettings:
    secret_key: str
    debug: bool
    allowed_hosts: list[str]

    def __init__(self) -> None:
        self.secret_key = _get_secret_or_env(
            "django_secret_key", "DJANGO_SECRET_KEY", "dev-secret-key-change-in-production"
        )
        self.debug = env("DEBUG")
        allowed_hosts_raw = env("ALLOWED_HOSTS", default="*")
        if isinstance(allowed_hosts_raw, str):
            allowed_hosts_iterable = allowed_hosts_raw.split(",")
        else:
            allowed_hosts_iterable = allowed_hosts_raw
        self.allowed_hosts = [h.strip() for h in allowed_hosts_iterable if h and h.strip()]


@dataclass
class DatabaseSettings:
    url: str

    def __init__(self) -> None:
        # Try to read postgres password from secret
        postgres_password = _read_secret_file("postgres_password")
        
        if postgres_password:
            # Build DATABASE_URL from environment variables and secret
            db_name = env("POSTGRES_DB", default="capyvagas")
            db_user = env("POSTGRES_USER", default="capyvagas_user")
            db_host = env("POSTGRES_HOST", default="db")
            db_port = env("POSTGRES_PORT", default="5432")
            self.url = f"postgres://{db_user}:{postgres_password}@{db_host}:{db_port}/{db_name}"
        else:
            # Fallback to DATABASE_URL or SQLite
            self.url = env("DATABASE_URL", default=f"sqlite:///{BASE_DIR}/db.sqlite3")


@dataclass
class RedisSettings:
    url: str

    def __init__(self) -> None:
        self.url = env("REDIS_URL")


@dataclass
class WahaSettings:
    base_url: str
    api_key: str
    session_name: str
    timeout_seconds: int

    def __init__(self) -> None:
        self.base_url = env("WAHA_URL")
        self.api_key = _get_secret_or_env("waha_api_key", "WAHA_API_KEY", "dev-api-key")
        self.session_name = env("WAHA_SESSION_NAME")
        self.timeout_seconds = env("WAHA_TIMEOUT_SECONDS")


@dataclass
class BotDashboardCredentials:
    username: str
    password: str

    def __init__(self) -> None:
        self.username = env("BOT_DASHBOARD_USERNAME")
        self.password = env("BOT_DASHBOARD_PASSWORD")


@dataclass
class DjangoAdminCredentials:
    username: str
    password: str

    def __init__(self) -> None:
        self.username = env("DJANGO_ADMIN_USERNAME")
        self.password = env("DJANGO_ADMIN_PASSWORD")


@dataclass
class AppConfig:
    django: DjangoSettings
    database: DatabaseSettings
    redis: RedisSettings
    waha: WahaSettings
    dashboard_credentials: BotDashboardCredentials
    admin_credentials: DjangoAdminCredentials

    def __init__(self) -> None:
        self.django = DjangoSettings()
        self.database = DatabaseSettings()
        self.redis = RedisSettings()
        self.waha = WahaSettings()
        self.dashboard_credentials = BotDashboardCredentials()
        self.admin_credentials = DjangoAdminCredentials()


settings = AppConfig()
