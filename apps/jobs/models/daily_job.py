from django.db import models

from apps.core.models import TimeStampedModel
from apps.courses.models import SearchTerm


class DailyJob(TimeStampedModel):
    """Vaga pré-fetched diariamente por SearchTerm via jobspy (BOT-01)."""

    search_term = models.ForeignKey(
        SearchTerm,
        on_delete=models.CASCADE,
        related_name="daily_jobs",
        help_text="Termo de busca que gerou esta vaga",
    )
    fetched_date = models.DateField(
        db_index=True,
        help_text="Data em que a vaga foi capturada (para limpeza e filtro)",
    )
    title = models.CharField(max_length=255, help_text="Título da vaga")
    company = models.CharField(max_length=255, help_text="Empresa")
    location = models.CharField(max_length=255, blank=True, default="")
    job_url = models.URLField(max_length=1000, help_text="Link direto para a vaga")
    description = models.TextField(blank=True, default="")
    job_type = models.CharField(max_length=50, blank=True, default="")
    is_manual = models.BooleanField(
        default=False,
        help_text="Vaga adicionada manualmente pelo admin (BOT-04)",
    )

    class Meta:
        ordering = ["-fetched_date", "title"]
        verbose_name = "Vaga do Dia"
        verbose_name_plural = "Vagas do Dia"
        indexes = [
            models.Index(fields=["fetched_date", "search_term"]),
            models.Index(fields=["search_term", "fetched_date"]),
        ]
        unique_together = [["search_term", "job_url", "fetched_date"]]

    def __str__(self) -> str:
        return f"{self.title} — {self.company} ({self.fetched_date})"
