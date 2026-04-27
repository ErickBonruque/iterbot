"""Testes do ApprovedCompanyRequiredMixin.

Garante que empresas PENDING/BLOCKED não conseguem acessar endpoints de CRUD
de vagas — alinhado com o fluxo de curadoria manual da milestone v1.0.
"""

from django.contrib.auth.models import User
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from apps.jobs.models import Company, CompanyStatus, Job, JobStatus

CACHES_LOCMEM = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
    }
}


@override_settings(CACHES=CACHES_LOCMEM)
class ApprovedCompanyRequiredMixinTests(TestCase):
    """Testa o gate de status nas views de Job."""

    def _make_user_with_company(self, username: str, status: str) -> tuple[User, Company]:
        user = User.objects.create_user(
            username=username, email=f"{username}@empresa.com", password="senha123"
        )
        company = Company.objects.create(
            user=user,
            cnpj=f"00.000.000/000{username[-1]}-00",
            nome=f"Empresa {username}",
            email=f"{username}@empresa.com",
            telefone="(41) 99999-0000",
            contato_nome="Responsavel",
            contato_cargo="Gerente",
            status=status,
        )
        return user, company

    def setUp(self):
        self.client = Client()

    def test_pending_company_blocked_from_creating_jobs(self):
        user, _ = self._make_user_with_company("pendente1", CompanyStatus.PENDING)
        self.client.force_login(user)

        response = self.client.get("/empresas/vagas/nova/")
        self.assertEqual(response.status_code, 403)

    def test_blocked_company_blocked_from_creating_jobs(self):
        user, _ = self._make_user_with_company("bloqueada2", CompanyStatus.BLOCKED)
        self.client.force_login(user)

        response = self.client.get("/empresas/vagas/nova/")
        self.assertEqual(response.status_code, 403)

    def test_approved_company_can_access_create_view(self):
        user, _ = self._make_user_with_company("aprovada3", CompanyStatus.APPROVED)
        self.client.force_login(user)

        response = self.client.get("/empresas/vagas/nova/")
        self.assertEqual(response.status_code, 200)

    def test_pending_company_blocked_from_editing_jobs(self):
        user, company = self._make_user_with_company("pendente4", CompanyStatus.PENDING)
        job = Job.objects.create(
            company=company,
            titulo="Vaga",
            descricao="Desc",
            tipo="estagio",
            status=JobStatus.PENDING,
        )
        self.client.force_login(user)

        response = self.client.get(f"/empresas/vagas/{job.pk}/editar/")
        self.assertEqual(response.status_code, 403)

    def test_pending_company_blocked_from_deleting_jobs(self):
        user, company = self._make_user_with_company("pendente5", CompanyStatus.PENDING)
        job = Job.objects.create(
            company=company,
            titulo="Vaga",
            descricao="Desc",
            tipo="estagio",
            status=JobStatus.PENDING,
        )
        self.client.force_login(user)

        response = self.client.get(reverse("companies:job_delete", kwargs={"pk": job.pk}))
        self.assertEqual(response.status_code, 403)

    def test_pending_company_can_access_profile(self):
        """Edição de perfil continua liberada para PENDING (apenas CRUD de vagas é gated)."""
        user, _ = self._make_user_with_company("pendente6", CompanyStatus.PENDING)
        self.client.force_login(user)

        response = self.client.get("/empresas/perfil/")
        self.assertEqual(response.status_code, 200)
