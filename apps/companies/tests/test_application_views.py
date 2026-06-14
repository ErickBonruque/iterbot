from django.contrib.auth.models import User
from django.test import Client, TestCase, override_settings

from apps.jobs.models import (
    ApplicationStatus,
    Company,
    CompanyStatus,
    Job,
    JobApplication,
    JobStatus,
)
from apps.users.models import UserProfile

CACHES_LOCMEM = {
    "default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"},
}


@override_settings(CACHES=CACHES_LOCMEM)
class JobApplicationsPortalTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username="empresa_cand", email="cand@empresa.com", password="TestPass123!"
        )
        self.company = Company.objects.create(
            user=self.user,
            cnpj="33.444.555/0001-10",
            nome="Empresa Cand",
            email="cand@empresa.com",
            telefone="(41) 90000-0000",
            contato_nome="Ana",
            contato_cargo="RH",
            status=CompanyStatus.APPROVED,
        )
        self.job = Job.objects.create(
            company=self.company,
            titulo="Vaga Portal",
            descricao="d",
            requisitos="r",
            tipo="Estágio",
            status=JobStatus.APPROVED,
        )
        self.student = UserProfile.objects.create(
            phone_number="5541999000111@c.us", ra="a7654321", is_authenticated_utfpr=True
        )
        self.application = JobApplication.objects.create(
            user=self.student,
            job=self.job,
            profile_snapshot={"periodo": "5º", "skills": "Python"},
        )

    def test_list_requires_login(self):
        response = self.client.get("/empresas/candidaturas/")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/empresas/login/", response.url)

    def test_list_shows_company_applications(self):
        self.client.force_login(self.user)
        response = self.client.get("/empresas/candidaturas/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Vaga Portal")
        self.assertContains(response, "Python")

    def test_list_excludes_other_companies(self):
        other_user = User.objects.create_user(
            username="outra", email="outra@empresa.com", password="TestPass123!"
        )
        other_company = Company.objects.create(
            user=other_user,
            cnpj="99.888.777/0001-66",
            nome="Outra Empresa",
            email="outra@empresa.com",
            telefone="(41) 91111-1111",
            contato_nome="X",
            contato_cargo="Y",
            status=CompanyStatus.APPROVED,
        )
        other_job = Job.objects.create(
            company=other_company,
            titulo="Vaga Alheia",
            descricao="d",
            tipo="CLT",
            status=JobStatus.APPROVED,
        )
        JobApplication.objects.create(user=self.student, job=other_job)

        self.client.force_login(self.user)
        response = self.client.get("/empresas/candidaturas/")
        self.assertContains(response, "Vaga Portal")
        self.assertNotContains(response, "Vaga Alheia")

    def test_status_update(self):
        self.client.force_login(self.user)
        response = self.client.post(
            f"/empresas/candidaturas/{self.application.pk}/status/",
            {"status": ApplicationStatus.CONTATADO},
        )
        self.assertEqual(response.status_code, 302)
        self.application.refresh_from_db()
        self.assertEqual(self.application.status, ApplicationStatus.CONTATADO)

    def test_status_update_rejects_other_company(self):
        other_user = User.objects.create_user(
            username="intruso", email="intruso@empresa.com", password="TestPass123!"
        )
        Company.objects.create(
            user=other_user,
            cnpj="11.111.111/0001-11",
            nome="Intruso",
            email="intruso@empresa.com",
            telefone="(41) 92222-2222",
            contato_nome="I",
            contato_cargo="I",
            status=CompanyStatus.APPROVED,
        )
        self.client.force_login(other_user)
        response = self.client.post(
            f"/empresas/candidaturas/{self.application.pk}/status/",
            {"status": ApplicationStatus.REJEITADA},
        )
        self.assertEqual(response.status_code, 403)
        self.application.refresh_from_db()
        self.assertEqual(self.application.status, ApplicationStatus.PENDING)
