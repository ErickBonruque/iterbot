from unittest.mock import patch

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

    def _abrir(self):
        self.client.force_login(self.user)
        return self.client.get("/empresas/candidaturas/")

    def test_candidaturas_whatsapp_formatado_com_link(self):
        self.student.phone_number = "5545999990000@c.us"
        self.student.save()

        response = self._abrir()

        self.assertContains(response, "(45) 99999-0000")
        self.assertContains(response, "https://wa.me/5545999990000")
        self.assertNotContains(response, "@c.us")

    def test_candidaturas_whatsapp_que_nao_e_telefone_nao_gera_link(self):
        self.student.phone_number = "123456789012345@lid"
        self.student.save()

        response = self._abrir()

        self.assertNotContains(response, "wa.me")
        self.assertNotContains(response, "@lid")
        self.assertContains(response, "WhatsApp indisponível")

    def test_candidaturas_email_mailto(self):
        self.student.email = "aluno@alunos.utfpr.edu.br"
        self.student.save()

        response = self._abrir()

        self.assertContains(response, 'href="mailto:aluno@alunos.utfpr.edu.br"')

    def test_candidaturas_mostra_ra_curso_e_periodo(self):
        from apps.courses.models import Course

        self.student.course = Course.objects.create(name="Ciência da Computação")
        self.student.save()

        response = self._abrir()

        self.assertContains(response, "RA a7654321")
        self.assertContains(response, "Ciência da Computação")
        self.assertContains(response, "5º")

    def test_candidaturas_data_legivel(self):
        response = self._abrir()

        self.assertRegex(response.content.decode(), r"\d{2}/\d{2}/\d{4} às \d{2}:\d{2}")

    def test_candidaturas_usa_selo_e_layout_do_portal(self):
        response = self._abrir()

        self.assertContains(response, "css/portal.css")
        self.assertContains(response, 'class="st st-nova"')
        self.assertContains(response, 'class="ativo" aria-current="page">Candidaturas')

    def test_candidaturas_seletor_de_status_lista_todas_as_opcoes(self):
        response = self._abrir()

        for rotulo in ["Pendente", "Vista", "Contatado", "Rejeitada"]:
            self.assertContains(response, f">{rotulo}</option>")

    def test_candidaturas_sem_nenhuma_mostra_estado_vazio(self):
        JobApplication.objects.all().delete()

        response = self._abrir()

        self.assertContains(response, "Nenhuma candidatura")

    def test_candidaturas_numero_de_consultas_nao_cresce_com_a_lista(self):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        from apps.courses.models import Course

        # Login uma vez, fora da medição: o login em si grava sessão e last_login.
        self.client.force_login(self.user)

        def consultas():
            # O middleware de logging grava uma métrica de latência em 10% das requisições
            # (random.random() < 0.1): um INSERT extra aleatório. Fixa o sorteio em "não grava".
            with (
                patch("infra.middleware.structured_logging.random.random", return_value=1.0),
                CaptureQueriesContext(connection) as ctx,
            ):
                self.client.get("/empresas/candidaturas/")
            return [q["sql"] for q in ctx.captured_queries]

        curso = Course.objects.create(name="Curso Consultas")
        self.student.course = curso
        self.student.save()
        consultas()  # aquecimento: a primeira requisição cria sessão e popula caches
        antes = consultas()
        for i in range(5):
            aluno = UserProfile.objects.create(
                phone_number=f"55459999{i:05d}@c.us", ra=f"a900000{i}", course=curso
            )
            JobApplication.objects.create(user=aluno, job=self.job)
        depois = consultas()

        def resumo(sqls):
            return "\n".join(f"  {sql[:110]}" for sql in sqls)

        self.assertEqual(
            len(depois),
            len(antes),
            f"ANTES ({len(antes)}):\n{resumo(antes)}\nDEPOIS ({len(depois)}):\n{resumo(depois)}",
        )

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
