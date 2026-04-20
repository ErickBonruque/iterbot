from dataclasses import dataclass

from config._helpers import env


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
