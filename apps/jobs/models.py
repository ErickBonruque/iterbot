from django.db import models
from apps.core.models import TimeStampedModel
from apps.users.models import UserProfile


class JobSearchLog(TimeStampedModel):
    """
    Log de buscas por vagas realizadas pelos usuários.
    """
    user = models.ForeignKey(
        UserProfile,
        on_delete=models.CASCADE,
        related_name='job_searches',
        help_text="Usuário que realizou a busca"
    )
    search_term = models.CharField(
        max_length=255,
        help_text="Termo de busca utilizado"
    )
    location = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="Localização da busca"
    )
    job_type = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        help_text="Tipo de vaga (estágio, CLT, etc.)"
    )
    results_count = models.IntegerField(
        default=0,
        help_text="Número de resultados encontrados"
    )
    filters = models.JSONField(
        default=dict,
        blank=True,
        help_text="Filtros aplicados na busca"
    )
    results_preview = models.JSONField(
        default=list,
        blank=True,
        help_text="Preview dos primeiros resultados (máx 5)"
    )
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Log de Busca de Vagas'
        verbose_name_plural = 'Logs de Buscas de Vagas'
        indexes = [
            models.Index(fields=['-created_at']),
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['search_term']),
        ]
    
    def __str__(self):
        return f"{self.user.phone_number}: {self.search_term} ({self.results_count} resultados)"
