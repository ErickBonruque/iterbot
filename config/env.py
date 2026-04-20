from dataclasses import dataclass

from config._helpers import BASE_DIR, _get_secret_or_env, _read_secret_file, env
from config.aws_settings import AwsSettings
from config.credentials import BotDashboardCredentials, DjangoAdminCredentials
from config.django_settings import DatabaseSettings, DjangoSettings, RedisSettings
from config.email_settings import EmailSettings
from config.waha_settings import WahaDashboardCredentials, WahaSettings, WahaSwaggerCredentials


@dataclass
class AppConfig:
    django: DjangoSettings
    database: DatabaseSettings
    redis: RedisSettings
    waha: WahaSettings
    dashboard_credentials: BotDashboardCredentials
    admin_credentials: DjangoAdminCredentials
    waha_dashboard_credentials: WahaDashboardCredentials
    waha_swagger_credentials: WahaSwaggerCredentials
    email: EmailSettings
    aws: AwsSettings

    def __init__(self) -> None:
        self.django = DjangoSettings()
        self.database = DatabaseSettings()
        self.redis = RedisSettings()
        self.waha = WahaSettings()
        self.dashboard_credentials = BotDashboardCredentials()
        self.admin_credentials = DjangoAdminCredentials()
        self.waha_dashboard_credentials = WahaDashboardCredentials()
        self.waha_swagger_credentials = WahaSwaggerCredentials()
        self.email = EmailSettings()
        self.aws = AwsSettings()


settings = AppConfig()

__all__ = [
    "BASE_DIR",
    "env",
    "_read_secret_file",
    "_get_secret_or_env",
    "DjangoSettings",
    "DatabaseSettings",
    "RedisSettings",
    "WahaSettings",
    "WahaDashboardCredentials",
    "WahaSwaggerCredentials",
    "EmailSettings",
    "AwsSettings",
    "DjangoAdminCredentials",
    "BotDashboardCredentials",
    "AppConfig",
    "settings",
]
