from dataclasses import dataclass

from config._helpers import BASE_DIR, _get_secret_or_env, _read_secret_file, env


@dataclass
class DjangoSettings:
    secret_key: str
    debug: bool
    allowed_hosts: list[str]
    portal_base_url: str
    encryption_key: str

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

        # PORTAL_BASE_URL: lê diretamente do env. Se ausente ou vazio, deriva de DOMAIN.
        # Isso garante que a URL enviada pelo bot seja sempre o domínio atual da EC2,
        # mesmo quando apenas DOMAIN é atualizado e PORTAL_BASE_URL não é redefinido.
        portal_base_url = env("PORTAL_BASE_URL", default="")
        if not portal_base_url:
            domain = env("DOMAIN", default="localhost")
            if domain and domain != "localhost":
                portal_base_url = f"https://{domain}"
            else:
                portal_base_url = f"http://{domain}"
        self.portal_base_url = portal_base_url

        # Chave dedicada para criptografia de campos sensíveis.
        # Lida de Docker secret "encryption_key" ou variável ENCRYPTION_KEY.
        # Se ausente, encryption.py fará fallback para SECRET_KEY (retrocompat).
        self.encryption_key = _get_secret_or_env("encryption_key", "ENCRYPTION_KEY", "")


@dataclass
class DatabaseSettings:
    url: str

    def __init__(self) -> None:
        postgres_password = _read_secret_file("postgres_password")

        if postgres_password:
            db_name = env("POSTGRES_DB", default="iterbot")
            db_user = env("POSTGRES_USER", default="iterbot_user")
            db_host = env("POSTGRES_HOST", default="db")
            db_port = env("POSTGRES_PORT", default="5432")
            self.url = f"postgres://{db_user}:{postgres_password}@{db_host}:{db_port}/{db_name}"
        else:
            self.url = env("DATABASE_URL", default=f"sqlite:///{BASE_DIR}/db.sqlite3")


@dataclass
class RedisSettings:
    url: str

    def __init__(self) -> None:
        self.url = env("REDIS_URL")
