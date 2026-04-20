from dataclasses import dataclass

from config._helpers import _get_secret_or_env, env


@dataclass
class WahaSettings:
    base_url: str
    api_key: str
    session_name: str
    timeout_seconds: int

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        session_name: str | None = None,
        timeout_seconds: int | None = None,
    ) -> None:
        self.base_url = base_url if base_url is not None else env("WAHA_URL")
        self.api_key = (
            api_key
            if api_key is not None
            else _get_secret_or_env("waha_api_key", "WAHA_API_KEY", "dev-api-key")
        )
        self.session_name = session_name if session_name is not None else env("WAHA_SESSION_NAME")
        self.timeout_seconds = (
            timeout_seconds if timeout_seconds is not None else env("WAHA_TIMEOUT_SECONDS")
        )


@dataclass
class WahaDashboardCredentials:
    username: str
    password: str

    def __init__(self) -> None:
        self.username = env("WAHA_DASHBOARD_USERNAME")
        self.password = env("WAHA_DASHBOARD_PASSWORD")


@dataclass
class WahaSwaggerCredentials:
    username: str
    password: str

    def __init__(self) -> None:
        self.username = env("WHATSAPP_SWAGGER_USERNAME")
        self.password = env("WHATSAPP_SWAGGER_PASSWORD")
