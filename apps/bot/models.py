from django.db import models
from django.db.models import Avg
from apps.core.models import TimeStampedModel
from apps.users.models import UserProfile
from config.env import WahaSettings, settings


class BotHealthCheck(TimeStampedModel):
    """
    Registro de verificações de saúde do bot WAHA.
    """
    STATUS_CHOICES = (
        ('online', 'Online'),
        ('offline', 'Offline'),
        ('error', 'Erro'),
    )
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, help_text="Status do bot")
    response_time = models.FloatField(null=True, blank=True, help_text="Tempo de resposta em ms")
    error_message = models.TextField(null=True, blank=True, help_text="Mensagem de erro (se houver)")
    session_status = models.CharField(max_length=50, default='unknown', help_text="Status da sessão WAHA")
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Verificação de Saúde do Bot'
        verbose_name_plural = 'Verificações de Saúde do Bot'
        indexes = [
            models.Index(fields=['-created_at']),
            models.Index(fields=['status']),
        ]
    
    def __str__(self):
        return f"{self.status} - {self.created_at.strftime('%Y-%m-%d %H:%M:%S')}"


class BotMetrics(TimeStampedModel):
    """
    Métricas personalizadas do bot.
    """
    metric_name = models.CharField(max_length=100, help_text="Nome da métrica")
    value = models.FloatField(help_text="Valor da métrica")
    metadata = models.JSONField(null=True, blank=True, help_text="Metadados adicionais")
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Métrica do Bot'
        verbose_name_plural = 'Métricas do Bot'
        indexes = [
            models.Index(fields=['metric_name', '-created_at']),
        ]
    
    def __str__(self):
        return f"{self.metric_name}: {self.value}"


class InteractionLog(TimeStampedModel):
    """
    Log de mensagens trocadas entre usuário e bot.
    """
    MESSAGE_TYPES = (
        ('SENT', 'Enviada pelo Bot'),
        ('RECEIVED', 'Recebida do Usuário'),
    )

    user = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name='interactions')
    message_content = models.TextField(help_text="Conteúdo da mensagem")
    message_type = models.CharField(max_length=10, choices=MESSAGE_TYPES)
    session_id = models.CharField(max_length=100, default='default', help_text="ID da sessão WAHA")
    metadata = models.JSONField(null=True, blank=True, help_text="Metadados adicionais da mensagem")
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Log de Interação'
        verbose_name_plural = 'Logs de Interações'
        indexes = [
            models.Index(fields=['-created_at']),
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['message_type']),
        ]

    def __str__(self):
        return f"[{self.message_type}] {self.user.phone_number}: {self.message_content[:50]}..."


class BotConfiguration(TimeStampedModel):
    """Configurações persistentes do bot controladas pelo dashboard."""

    waha_url = models.URLField(blank=True)
    waha_api_key = models.CharField(max_length=255, blank=True)
    waha_session = models.CharField(max_length=100, blank=True)
    dashboard_username = models.CharField(max_length=150, blank=True)
    dashboard_password = models.CharField(max_length=150, blank=True)
    admin_username = models.CharField(max_length=150, blank=True)
    admin_password = models.CharField(max_length=150, blank=True)

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


class BotMessage(TimeStampedModel):
    """
    Mensagens configuráveis do bot.
    """
    KEY_CHOICES = (
        ('welcome', 'Boas-vindas / Menu'),
        ('login_prompt', 'Solicitar Login'),
        ('login_success', 'Login com Sucesso'),
        ('login_error', 'Erro no Login'),
        ('logout_success', 'Logout com Sucesso'),
        ('course_selection', 'Seleção de Curso'),
        ('term_selection', 'Seleção de Termo'),
        ('no_results', 'Sem Resultados'),
        ('unknown_command', 'Comando Desconhecido'),
        ('error_generic', 'Erro Genérico'),
    )

    key = models.CharField(max_length=50, choices=KEY_CHOICES, unique=True, help_text="Chave identificadora da mensagem")
    text = models.TextField(help_text="Conteúdo da mensagem. Use {variaveis} para interpolação se necessário.")
    description = models.CharField(max_length=255, blank=True, help_text="Descrição do uso desta mensagem")

    class Meta:
        verbose_name = 'Mensagem do Bot'
        verbose_name_plural = 'Mensagens do Bot'
        ordering = ['key']

    def __str__(self):
        return f"{self.get_key_display()}"

