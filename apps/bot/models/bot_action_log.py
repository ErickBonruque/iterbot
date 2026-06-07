from django.db import models

from apps.core.models import TimeStampedModel
from apps.users.models import UserProfile


class BotActionLog(TimeStampedModel):
    ACTION_CHOICES = [
        ("SEARCH", "Busca de Vagas"),
        ("MENU", "Menu"),
        ("AUTH", "Autenticação"),
        ("REVIEW", "Review de Vagas"),
        ("WAHA_SEND", "Envio WAHA"),
    ]
    STATUS_CHOICES = [
        ("SUCCESS", "Sucesso"),
        ("ERROR", "Erro"),
        ("TIMEOUT", "Timeout"),
    ]
    ERROR_TYPE_CHOICES = [
        ("EXCEPTION", "Exceção"),
        ("WAHA_TIMEOUT", "Timeout WAHA"),
        ("WAHA_SEND_FAIL", "Falha de Envio WAHA"),
    ]

    user = models.ForeignKey(
        UserProfile,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="action_logs",
    )
    action_type = models.CharField(max_length=20, choices=ACTION_CHOICES)
    search_term = models.CharField(max_length=255, null=True, blank=True)
    jobs_found = models.IntegerField(null=True, blank=True)
    duration_ms = models.IntegerField(null=True, blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="SUCCESS")
    error_message = models.TextField(null=True, blank=True)
    error_type = models.CharField(
        max_length=20, choices=ERROR_TYPE_CHOICES, null=True, blank=True
    )
    metadata = models.JSONField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Log de Ação do Bot"
        verbose_name_plural = "Logs de Ações do Bot"
        indexes = [
            models.Index(fields=["action_type", "-created_at"]),
            models.Index(fields=["status", "-created_at"]),
            models.Index(fields=["user", "-created_at"]),
        ]

    def __str__(self) -> str:
        return f"[{self.action_type}] {self.status} @ {self.created_at}"
