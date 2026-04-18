from django.db import models

from apps.core.models import TimeStampedModel


class BotHealthCheck(TimeStampedModel):
    """
    Registro de verificações de saúde do bot WAHA.
    """

    STATUS_CHOICES = (
        ("online", "Online"),
        ("offline", "Offline"),
        ("error", "Erro"),
    )

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, help_text="Status do bot")
    response_time = models.FloatField(null=True, blank=True, help_text="Tempo de resposta em ms")
    error_message = models.TextField(
        null=True, blank=True, help_text="Mensagem de erro (se houver)"
    )
    session_status = models.CharField(
        max_length=50, default="unknown", help_text="Status da sessão WAHA"
    )

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Verificação de Saúde do Bot"
        verbose_name_plural = "Verificações de Saúde do Bot"
        indexes = [
            models.Index(fields=["-created_at"]),
            models.Index(fields=["status"]),
        ]

    def __str__(self):
        return f"{self.status} - {self.created_at.strftime('%Y-%m-%d %H:%M:%S')}"
