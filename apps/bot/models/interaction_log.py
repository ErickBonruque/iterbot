from django.db import models

from apps.core.models import TimeStampedModel
from apps.users.models import UserProfile


class InteractionLog(TimeStampedModel):
    """
    Log de mensagens trocadas entre usuário e bot.
    """

    MESSAGE_TYPES = (
        ("SENT", "Enviada pelo Bot"),
        ("RECEIVED", "Recebida do Usuário"),
    )

    user = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name="interactions")
    message_content = models.TextField(help_text="Conteúdo da mensagem")
    message_type = models.CharField(max_length=10, choices=MESSAGE_TYPES)
    session_id = models.CharField(max_length=100, default="default", help_text="ID da sessão WAHA")
    metadata = models.JSONField(null=True, blank=True, help_text="Metadados adicionais da mensagem")

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Log de Interação"
        verbose_name_plural = "Logs de Interações"
        indexes = [
            models.Index(fields=["-created_at"]),
            models.Index(fields=["user", "-created_at"]),
            models.Index(fields=["message_type"]),
        ]

    def __str__(self):
        return f"[{self.message_type}] {self.user.phone_number}: {self.message_content[:50]}..."
