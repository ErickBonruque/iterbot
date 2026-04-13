from django.contrib.auth.models import User
from django.db import models

from apps.core.models import TimeStampedModel
from apps.jobs.validators import validate_cnpj
from apps.users.models import UserProfile


class CompanyStatus(models.TextChoices):
    PENDING = 'pending', 'Pendente'
    APPROVED = 'approved', 'Aprovada'
    BLOCKED = 'blocked', 'Bloqueada'


class JobStatus(models.TextChoices):
    DRAFT = 'draft', 'Rascunho'
    PENDING = 'pending', 'Pendente'
    APPROVED = 'approved', 'Aprovada'
    REJECTED = 'rejected', 'Rejeitada'
    EXPIRED = 'expired', 'Expirada'


class Company(TimeStampedModel):
    """
    Empresa local que cadastra vagas para alunos da UTFPR.
    """
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='company',
        null=True,
        blank=True,
        help_text="Usuario vinculado a esta empresa"
    )
    cnpj = models.CharField(
        max_length=18,
        unique=True,
        validators=[validate_cnpj],
        help_text="CNPJ da empresa (com ou sem máscara)"
    )
    nome = models.CharField(
        max_length=255,
        help_text="Razão social ou nome fantasia"
    )
    email = models.EmailField(
        help_text="E-mail de contato da empresa"
    )
    telefone = models.CharField(
        max_length=20,
        help_text="Telefone de contato (com DDD)"
    )
    endereco = models.TextField(
        blank=True,
        help_text="Endereço completo da empresa"
    )
    descricao = models.TextField(
        blank=True,
        help_text="Descrição sobre a empresa (opcional)"
    )
    contato_nome = models.CharField(
        max_length=255,
        help_text="Nome da pessoa responsável"
    )
    contato_cargo = models.CharField(
        max_length=100,
        help_text="Cargo da pessoa responsável"
    )
    status = models.CharField(
        max_length=20,
        choices=CompanyStatus.choices,
        default=CompanyStatus.PENDING,
        help_text="Status da empresa no sistema"
    )
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Empresa'
        verbose_name_plural = 'Empresas'
        indexes = [
            models.Index(fields=['-created_at']),
            models.Index(fields=['status']),
        ]
    
    def __str__(self):
        return f"{self.nome} ({self.cnpj})"


class Job(TimeStampedModel):
    """
    Vaga de estágio/emprego cadastrada por uma empresa.
    """
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name='jobs',
        help_text="Empresa que oferece a vaga"
    )
    titulo = models.CharField(
        max_length=255,
        help_text="Título da vaga"
    )
    descricao = models.TextField(
        help_text="Descrição detalhada da vaga"
    )
    requisitos = models.TextField(
        blank=True,
        help_text="Requisitos e qualificações necessárias"
    )
    salario = models.CharField(
        max_length=100,
        blank=True,
        help_text="Faixa salarial ou 'A combinar'"
    )
    tipo = models.CharField(
        max_length=50,
        help_text="Tipo da vaga (Estágio, CLT, PJ, etc.)"
    )
    status = models.CharField(
        max_length=20,
        choices=JobStatus.choices,
        default=JobStatus.DRAFT,
        help_text="Status da vaga no sistema"
    )
    rejection_reason = models.TextField(
        blank=True,
        null=True,
        help_text="Motivo da rejeição (preenchido automaticamente ao rejeitar)"
    )
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Vaga'
        verbose_name_plural = 'Vagas'
        indexes = [
            models.Index(fields=['-created_at']),
            models.Index(fields=['company', 'status']),
            models.Index(fields=['status']),
        ]
    
    def __str__(self):
        return f"{self.titulo} - {self.company.nome}"


class JobApplication(TimeStampedModel):
    """
    Candidatura de um aluno a uma vaga.
    """
    user = models.ForeignKey(
        UserProfile,
        on_delete=models.CASCADE,
        related_name='job_applications',
        help_text="Aluno que se candidatou"
    )
    job = models.ForeignKey(
        Job,
        on_delete=models.CASCADE,
        related_name='applications',
        help_text="Vaga para qual o aluno se candidatou"
    )
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Candidatura'
        verbose_name_plural = 'Candidaturas'
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'job'],
                name='unique_application_per_user_job'
            )
        ]
        indexes = [
            models.Index(fields=['-created_at']),
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['job', '-created_at']),
        ]
    
    def __str__(self):
        return f"{self.user} -> {self.job.titulo}"


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
