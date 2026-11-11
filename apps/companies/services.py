from collections import Counter
from dataclasses import dataclass

from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Count, QuerySet
from django.http import Http404
from django.shortcuts import get_object_or_404

from apps.jobs.models import (
    ApplicationStatus,
    Company,
    CompanyStatus,
    Job,
    JobApplication,
    JobStatus,
)


@dataclass
class DashboardSummary:
    """Dados do painel da empresa (ver ``CompaniesService.dashboard_summary``)."""

    new_applications: int
    jobs_pending: int
    jobs_rejected: int
    jobs_approved: int
    jobs: QuerySet[Job]
    recent_applications: list[JobApplication]


class CompaniesService:
    @staticmethod
    def get_user_company_or_none(user):
        try:
            return user.company
        except Exception:
            pass
        # Fallback: empresa criada no admin com mesmo email, sem user vinculado.
        # Auto-linka para que acessos futuros usem a FK reversa normal.
        company = Company.objects.filter(email=user.email, user__isnull=True).first()
        if company is not None:
            company.user = user
            company.save(update_fields=["user"])
        return company

    @staticmethod
    @transaction.atomic
    def create_company_for_user(user, cleaned_data):
        """Cria uma Company vinculada ao ``user``, sempre com status PENDING.

        Esta é a fonte única para criação de empresas — usada tanto pelo
        ``CompanySignupForm.save`` (signup novo) quanto pelo ``CompanyCreateView``
        (usuário existente sem empresa). Manter a lógica em um só lugar evita
        drift quando novos campos forem adicionados ao modelo.
        """
        return Company.objects.create(
            user=user,
            cnpj=cleaned_data["cnpj"],
            nome=cleaned_data["nome"],
            email=user.email,
            telefone=cleaned_data["telefone"],
            contato_nome=cleaned_data["contato_nome"],
            contato_cargo=cleaned_data["contato_cargo"],
            status=CompanyStatus.PENDING,
        )

    @staticmethod
    def prepare_job_for_creation(form_instance, user):
        form_instance.company = user.company
        form_instance.status = JobStatus.PENDING

    @staticmethod
    def prepare_job_for_update(job, changed):
        """Aplica a regra de reenvio antes de salvar uma edição de vaga.

        Se ``changed`` e a vaga estava aprovada ou recusada, ela volta para
        ``PENDING`` (e perde o motivo da recusa) para a UTFPR analisar de novo.
        Devolve ``True`` quando a vaga foi reenviada para análise.
        """
        if changed and job.status in {JobStatus.APPROVED, JobStatus.REJECTED}:
            job.status = JobStatus.PENDING
            job.rejection_reason = None
            return True
        return False

    @staticmethod
    def get_editable_job_or_403(job, user):
        return CompaniesService._validate_job_ownership(
            job=job,
            user=user,
            error_message="Você não tem permissão para editar esta vaga.",
        )

    @staticmethod
    def get_deletable_job_or_404(pk):
        job = get_object_or_404(Job, pk=pk)
        if job.status == JobStatus.REMOVED:
            raise Http404("Vaga já removida.")
        return job

    @staticmethod
    def get_deletable_job_for_user_or_403(pk, user):
        job = CompaniesService.get_deletable_job_or_404(pk)
        return CompaniesService._validate_job_ownership(
            job=job,
            user=user,
            error_message="Você não tem permissão para remover esta vaga.",
        )

    @staticmethod
    @transaction.atomic
    def soft_delete_job(pk, user):
        job = CompaniesService.get_deletable_job_for_user_or_403(pk=pk, user=user)
        job.status = JobStatus.REMOVED
        job.save(update_fields=["status"])
        return job

    @staticmethod
    def list_company_jobs(company):
        """Vagas visíveis da empresa (as removidas não voltam a aparecer)."""
        if company is None:
            return Job.objects.none()
        return (
            Job.objects.filter(company=company)
            .exclude(status=JobStatus.REMOVED)
            .order_by("-created_at")
        )

    @staticmethod
    def dashboard_summary(company):
        """Números, vagas e candidaturas recentes do painel, em 3 consultas fixas.

        ``jobs`` são as vagas não removidas (mais recente primeiro) com
        ``num_applications`` anotado; ``new_applications`` conta as candidaturas
        ``pending`` das vagas da empresa; ``recent_applications`` são as 5 últimas.
        Empresa sem vagas/candidaturas devolve zeros e listas vazias.
        """
        jobs = CompaniesService.list_company_jobs(company).annotate(
            num_applications=Count("applications")
        )
        # Iterar aqui avalia (e guarda em cache) a consulta das vagas: o template
        # reaproveita o resultado sem ir ao banco de novo.
        por_status = Counter(job.status for job in jobs)

        applications = JobApplication.objects.filter(job__company=company)
        return DashboardSummary(
            new_applications=applications.filter(status=ApplicationStatus.PENDING).count(),
            jobs_pending=por_status[JobStatus.PENDING.value],
            jobs_rejected=por_status[JobStatus.REJECTED.value],
            jobs_approved=por_status[JobStatus.APPROVED.value],
            jobs=jobs,
            recent_applications=list(
                applications.select_related("user", "user__course", "job").order_by("-created_at")[
                    :5
                ]
            ),
        )

    @staticmethod
    def list_company_applications(user):
        """Candidaturas das vagas da empresa do `user`, mais recentes primeiro."""
        company = CompaniesService.get_user_company_or_none(user)
        if company is None:
            return JobApplication.objects.none()
        return (
            JobApplication.objects.filter(job__company=company)
            .select_related("user", "job")
            .order_by("-created_at")
        )

    @staticmethod
    @transaction.atomic
    def update_application_status(pk, user, new_status):
        """Atualiza o status de uma candidatura, validando a posse pela empresa."""
        if new_status not in ApplicationStatus.values:
            raise PermissionDenied("Status inválido.")
        company = CompaniesService.get_user_company_or_none(user)
        application = get_object_or_404(
            JobApplication.objects.select_related("job__company"), pk=pk
        )
        if company is None or application.job.company_id != company.id:
            raise PermissionDenied("Você não tem permissão para alterar esta candidatura.")
        application.status = new_status
        application.save(update_fields=["status", "updated_at"])
        return application

    @staticmethod
    def _validate_job_ownership(job, user, error_message):
        try:
            user_company = user.company
        except Exception as err:
            raise PermissionDenied(error_message) from err

        if job.company != user_company:
            raise PermissionDenied(error_message)

        return job
