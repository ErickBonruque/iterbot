from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.http import Http404
from django.shortcuts import get_object_or_404

from apps.jobs.models import Company, CompanyStatus, Job, JobStatus


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
    def get_editable_job_or_403(job, user):
        return CompaniesService._validate_job_ownership(
            job=job,
            user=user,
            error_message="Voce nao tem permissao para editar esta vaga.",
        )

    @staticmethod
    def get_deletable_job_or_404(pk):
        job = get_object_or_404(Job, pk=pk)
        if job.status == JobStatus.REMOVED:
            raise Http404("Vaga ja removida.")
        return job

    @staticmethod
    def get_deletable_job_for_user_or_403(pk, user):
        job = CompaniesService.get_deletable_job_or_404(pk)
        return CompaniesService._validate_job_ownership(
            job=job,
            user=user,
            error_message="Voce nao tem permissao para remover esta vaga.",
        )

    @staticmethod
    @transaction.atomic
    def soft_delete_job(pk, user):
        job = CompaniesService.get_deletable_job_for_user_or_403(pk=pk, user=user)
        job.status = JobStatus.REMOVED
        job.save(update_fields=["status"])
        return job

    @staticmethod
    def _validate_job_ownership(job, user, error_message):
        try:
            user_company = user.company
        except Exception as err:
            raise PermissionDenied(error_message) from err

        if job.company != user_company:
            raise PermissionDenied(error_message)

        return job
