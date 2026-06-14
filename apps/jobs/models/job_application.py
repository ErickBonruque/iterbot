from django.db import models

from apps.core.models import TimeStampedModel
from apps.jobs.models.job import Job
from apps.users.models import UserProfile


class ApplicationStatus(models.TextChoices):
    PENDING = "pending", "Pendente"
    VISTA = "vista", "Vista"
    CONTATADO = "contatado", "Contatado"
    REJEITADA = "rejeitada", "Rejeitada"


class JobApplication(TimeStampedModel):
    """
    Candidatura de um aluno a uma vaga.
    """

    user = models.ForeignKey(
        UserProfile,
        on_delete=models.CASCADE,
        related_name="job_applications",
        help_text="Aluno que se candidatou",
    )
    job = models.ForeignKey(
        Job,
        on_delete=models.CASCADE,
        related_name="applications",
        help_text="Vaga para qual o aluno se candidatou",
    )
    status = models.CharField(
        max_length=20,
        choices=ApplicationStatus.choices,
        default=ApplicationStatus.PENDING,
        help_text="Status da candidatura no acompanhamento da empresa",
    )
    message = models.TextField(
        blank=True,
        help_text="Recado opcional do aluno para a empresa",
    )
    profile_snapshot = models.JSONField(
        default=dict,
        blank=True,
        help_text="Cópia do mini-perfil do aluno no momento da candidatura (histórico imutável)",
    )

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Candidatura"
        verbose_name_plural = "Candidaturas"
        constraints = [
            models.UniqueConstraint(fields=["user", "job"], name="unique_application_per_user_job")
        ]
        indexes = [
            models.Index(fields=["-created_at"]),
            models.Index(fields=["user", "-created_at"]),
            models.Index(fields=["job", "-created_at"]),
        ]

    def __str__(self):
        return f"{self.user} -> {self.job.titulo}"
