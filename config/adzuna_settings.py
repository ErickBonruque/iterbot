from dataclasses import dataclass

from config._helpers import _get_secret_or_env, env


@dataclass
class AdzunaSettings:
    """Credenciais da API Adzuna (fonte de vagas complementar ao jobspy).

    Sem `app_id`/`app_key` a busca na Adzuna é pulada com um aviso no log —
    os demais sites seguem funcionando.
    """

    app_id: str
    app_key: str
    country: str

    def __init__(self) -> None:
        self.app_id = env("ADZUNA_APP_ID")
        self.app_key = _get_secret_or_env("adzuna_app_key", "ADZUNA_APP_KEY", "")
        self.country = env("ADZUNA_COUNTRY")

    @property
    def configured(self) -> bool:
        return bool(self.app_id and self.app_key)
