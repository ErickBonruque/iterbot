from django.contrib.auth.models import User
from django.db import models

from apps.core.models import TimeStampedModel
from apps.jobs.validators import validate_cnpj


class CompanyStatus(models.TextChoices):
    PENDING = "pending", "Pendente"
    APPROVED = "approved", "Aprovada"
    BLOCKED = "blocked", "Bloqueada"


class Company(TimeStampedModel):
    """
    Empresa local que cadastra vagas para alunos da UTFPR.
    """

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="company",
        null=True,
        blank=True,
        help_text="Usuario vinculado a esta empresa",
    )
    cnpj = models.CharField(
        max_length=18,
        unique=True,
        validators=[validate_cnpj],
        help_text="CNPJ da empresa (com ou sem máscara)",
    )
    nome = models.CharField(max_length=255, help_text="Razão social ou nome fantasia")
    email = models.EmailField(help_text="E-mail de contato da empresa")
    telefone = models.CharField(max_length=20, help_text="Telefone de contato (com DDD)")
    endereco = models.TextField(blank=True, help_text="Endereço completo da empresa")
    descricao = models.TextField(blank=True, help_text="Descrição sobre a empresa (opcional)")
    contato_nome = models.CharField(max_length=255, help_text="Nome da pessoa responsável")
    contato_cargo = models.CharField(max_length=100, help_text="Cargo da pessoa responsável")
    status = models.CharField(
        max_length=20,
        choices=CompanyStatus.choices,
        default=CompanyStatus.PENDING,
        help_text="Status da empresa no sistema",
    )

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Empresa"
        verbose_name_plural = "Empresas"
        indexes = [
            models.Index(fields=["-created_at"]),
            models.Index(fields=["status"]),
        ]

    def __str__(self):
        return f"{self.nome} ({self.cnpj})"
