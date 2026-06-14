from django.db import models
from django.db.models import Q

from apps.core.models import TimeStampedModel
from apps.jobs.models.company import Company


class JobStatus(models.TextChoices):
    DRAFT = "draft", "Rascunho"
    PENDING = "pending", "Pendente"
    APPROVED = "approved", "Aprovada"
    REJECTED = "rejected", "Rejeitada"
    EXPIRED = "expired", "Expirada"
    REMOVED = "removed", "Removida"


class JobQuerySet(models.QuerySet):
    """QuerySet de `Job` com a regra centralizada de áreas.

    Convenção do projeto (travada): uma vaga **sem nenhuma área** é ofertada
    para **todas as áreas**. Toda filtragem por área (resumo semanal, menu do
    aluno, etc.) deve passar por `for_area` para não reimplementar a regra.
    """

    def for_area(self, area):
        """Vagas ofertadas para `area`: as que incluem a área **ou** as que não
        têm nenhuma área (= todas).

        Se `area` for `None` (ex.: curso do aluno sem área definida), retorna
        apenas as vagas "para todas as áreas".
        """
        if area is None:
            return self.filter(areas__isnull=True)
        return self.filter(Q(areas=area) | Q(areas__isnull=True)).distinct()


class Job(TimeStampedModel):
    """
    Vaga de estágio/emprego cadastrada por uma empresa.
    """

    objects = JobQuerySet.as_manager()

    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="jobs",
        help_text="Empresa que oferece a vaga",
    )
    titulo = models.CharField(max_length=255, help_text="Título da vaga")
    descricao = models.TextField(help_text="Descrição detalhada da vaga")
    requisitos = models.TextField(blank=True, help_text="Requisitos e qualificações necessárias")
    salario = models.CharField(
        max_length=100, blank=True, help_text="Faixa salarial ou 'A combinar'"
    )
    tipo = models.CharField(max_length=50, help_text="Tipo da vaga (Estágio, CLT, PJ, etc.)")
    status = models.CharField(
        max_length=20,
        choices=JobStatus.choices,
        default=JobStatus.DRAFT,
        help_text="Status da vaga no sistema",
    )
    rejection_reason = models.TextField(
        blank=True,
        null=True,
        help_text="Motivo da rejeição (preenchido automaticamente ao rejeitar)",
    )
    areas = models.ManyToManyField(
        "courses.Area",
        blank=True,
        related_name="jobs",
        verbose_name="Áreas",
        help_text="Áreas para as quais a vaga é ofertada. Vazio = todas.",
    )

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Vaga"
        verbose_name_plural = "Vagas"
        indexes = [
            models.Index(fields=["-created_at"]),
            models.Index(fields=["company", "status"]),
            models.Index(fields=["status"]),
        ]

    def __str__(self):
        return f"{self.titulo} - {self.company.nome}"
