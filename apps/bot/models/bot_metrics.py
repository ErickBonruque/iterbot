from django.db import models

from apps.core.models import TimeStampedModel


class BotMetrics(TimeStampedModel):
    """
    Métricas personalizadas do bot.
    """

    metric_name = models.CharField(max_length=100, help_text="Nome da métrica")
    value = models.FloatField(help_text="Valor da métrica")
    metadata = models.JSONField(null=True, blank=True, help_text="Metadados adicionais")

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Métrica do Bot"
        verbose_name_plural = "Métricas do Bot"
        indexes = [
            models.Index(fields=["metric_name", "-created_at"]),
        ]

    def __str__(self):
        return f"{self.metric_name}: {self.value}"
