from django.db import models

from apps.core.models import TimeStampedModel
from apps.jobs.models.job import Job
from apps.users.models import UserProfile


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
