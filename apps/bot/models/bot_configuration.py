from django.db import models

from apps.core.models import TimeStampedModel
from config.env import WahaSettings, settings
from infra.security.fields import EncryptedCharField


class BotConfiguration(TimeStampedModel):
    """Configurações persistentes do bot controladas pelo dashboard."""

    waha_url = models.URLField(blank=True)
    waha_api_key = EncryptedCharField(max_length=512, blank=True)
    waha_session = models.CharField(max_length=100, blank=True)
    dashboard_username = models.CharField(max_length=150, blank=True)
    dashboard_password = EncryptedCharField(max_length=512, blank=True)
    admin_username = models.CharField(max_length=150, blank=True)
    admin_password = EncryptedCharField(max_length=512, blank=True)

    class Meta:
        verbose_name = "Configuração do Bot"
        verbose_name_plural = "Configurações do Bot"

    def to_waha_settings(self) -> WahaSettings:
        """Converte registro em objeto de configuração da integração WAHA."""

        return WahaSettings(
            base_url=self.waha_url,
            api_key=self.waha_api_key,
            session_name=self.waha_session,
        )

    @classmethod
    def get_active(cls) -> WahaSettings:
        """Retorna a configuração mais recente ou valores padrão."""

        instance = cls.objects.order_by("-created_at").first()
        return instance.to_waha_settings() if instance else WahaSettings()

    @classmethod
    def defaults(cls) -> "BotConfiguration":
        """Configuração preenchida com valores de ambiente para bootstrap."""

        return cls(
            waha_url=settings.waha.base_url,
            waha_api_key=settings.waha.api_key,
            waha_session=settings.waha.session_name,
            dashboard_username=settings.dashboard_credentials.username,
            dashboard_password=settings.dashboard_credentials.password,
            admin_username=settings.admin_credentials.username,
            admin_password=settings.admin_credentials.password,
        )
