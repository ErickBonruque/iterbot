from allauth.account.models import EmailAddress
from django.contrib.auth.models import User
from django.db import connection
from django.test import Client, TestCase, override_settings
from django.test.utils import CaptureQueriesContext

from apps.companies.services import CompaniesService
from apps.courses.models import Course
from apps.jobs.models import ApplicationStatus, Company, CompanyStatus, JobStatus
from apps.jobs.tests.factories import CompanyFactory, JobApplicationFactory, JobFactory
from apps.users.tests.factories import UserProfileFactory

CACHES_LOCMEM = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}

PAINEL = "/empresas/painel/"


def _usuario_com_empresa(username="dono", status=CompanyStatus.APPROVED, cnpj="11.222.333/0001-81"):
    user = User.objects.create_user(
        username=username, email=f"{username}@empresa.com", password="TestPass123!"
    )
    company = CompanyFactory(user=user, status=status, cnpj=cnpj, contato_nome="Mariana")
    return user, company


class TestDashboardSummary(TestCase):
    """CompaniesService.dashboard_summary: números, vagas e candidaturas recentes."""

    def setUp(self):
        _, self.company = _usuario_com_empresa()

    def test_resumo_conta_por_status(self):
        aprovada = JobFactory(company=self.company, status=JobStatus.APPROVED)
        JobFactory(company=self.company, status=JobStatus.PENDING)
        JobFactory(company=self.company, status=JobStatus.REJECTED)
        JobFactory(company=self.company, status=JobStatus.REMOVED, titulo="Removida")
        JobApplicationFactory(job=aprovada, user=UserProfileFactory())
        JobApplicationFactory(
            job=aprovada, user=UserProfileFactory(), status=ApplicationStatus.VISTA
        )

        resumo = CompaniesService.dashboard_summary(self.company)

        self.assertEqual(
            (
                resumo.new_applications,
                resumo.jobs_pending,
                resumo.jobs_rejected,
                resumo.jobs_approved,
            ),
            (1, 1, 1, 1),
        )
        self.assertEqual(len(resumo.jobs), 3)
        self.assertNotIn("Removida", [j.titulo for j in resumo.jobs])

    def test_num_applications_por_vaga(self):
        com_duas = JobFactory(company=self.company, titulo="Com duas")
        JobFactory(company=self.company, titulo="Sem nenhuma")
        JobApplicationFactory(job=com_duas, user=UserProfileFactory())
        JobApplicationFactory(job=com_duas, user=UserProfileFactory())

        resumo = CompaniesService.dashboard_summary(self.company)

        self.assertEqual(
            {j.titulo: j.num_applications for j in resumo.jobs}, {"Com duas": 2, "Sem nenhuma": 0}
        )

    def test_nao_mistura_dados_de_outra_empresa(self):
        _, outra = _usuario_com_empresa("outro", cnpj="22.333.444/0001-81")
        vaga_alheia = JobFactory(company=outra, titulo="Alheia", status=JobStatus.PENDING)
        JobApplicationFactory(job=vaga_alheia, user=UserProfileFactory())

        resumo = CompaniesService.dashboard_summary(self.company)

        self.assertEqual(resumo.new_applications, 0)
        self.assertEqual(resumo.jobs_pending, 0)
        self.assertEqual(list(resumo.jobs), [])
        self.assertEqual(resumo.recent_applications, [])

    def test_recentes_sao_as_cinco_ultimas_mais_novas_primeiro(self):
        vaga = JobFactory(company=self.company)
        criadas = [JobApplicationFactory(job=vaga, user=UserProfileFactory()) for _ in range(7)]

        resumo = CompaniesService.dashboard_summary(self.company)

        self.assertEqual(
            [a.pk for a in resumo.recent_applications], [a.pk for a in reversed(criadas)][:5]
        )

    def test_resumo_sem_n_mais_1(self):
        def consultas(qtd_vagas):
            company = CompanyFactory(
                user=User.objects.create_user(
                    username=f"u{qtd_vagas}", email=f"u{qtd_vagas}@empresa.com", password="x"
                ),
                cnpj=f"33.444.555/000{qtd_vagas}-00",
            )
            curso = Course.objects.create(name=f"Curso {qtd_vagas}")
            for _ in range(qtd_vagas):
                vaga = JobFactory(company=company)
                aluno = UserProfileFactory(course=curso)
                JobApplicationFactory(job=vaga, user=aluno)
            with CaptureQueriesContext(connection) as ctx:
                resumo = CompaniesService.dashboard_summary(company)
                for vaga in resumo.jobs:
                    vaga.num_applications  # noqa: B018
                for candidatura in resumo.recent_applications:
                    candidatura.user.course.name  # noqa: B018
                    candidatura.job.titulo  # noqa: B018
            return len(ctx)

        self.assertEqual(consultas(1), consultas(5))

    def test_resumo_vazio(self):
        resumo = CompaniesService.dashboard_summary(self.company)

        self.assertEqual(
            (
                resumo.new_applications,
                resumo.jobs_pending,
                resumo.jobs_rejected,
                resumo.jobs_approved,
            ),
            (0, 0, 0, 0),
        )
        self.assertEqual(list(resumo.jobs), [])
        self.assertEqual(resumo.recent_applications, [])


@override_settings(CACHES=CACHES_LOCMEM)
class TestDashboardView(TestCase):
    """GET /empresas/painel/ no navegador."""

    def setUp(self):
        self.client = Client()
        self.user, self.company = _usuario_com_empresa()

    def _abrir(self):
        self.client.force_login(self.user)
        return self.client.get(PAINEL)

    def test_painel_mostra_cabecalho_e_numeros(self):
        vaga = JobFactory(company=self.company, status=JobStatus.APPROVED)
        JobApplicationFactory(job=vaga, user=UserProfileFactory())

        response = self._abrir()

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Olá, Mariana")
        self.assertContains(response, self.company.nome)
        self.assertContains(response, "Publicar nova vaga")
        self.assertContains(response, 'href="/empresas/vagas/nova/"')
        self.assertContains(response, "candidatura nova")
        self.assertContains(response, "vaga publicada")

    def test_painel_mostra_motivo_da_recusa(self):
        JobFactory(
            company=self.company,
            status=JobStatus.REJECTED,
            rejection_reason="Vaga fora do escopo de estágio da UTFPR.",
        )

        response = self._abrir()

        self.assertContains(response, "Recusada")
        self.assertContains(response, "Vaga fora do escopo de estágio da UTFPR.")
        self.assertContains(response, "Editar e reenviar")

    def test_painel_mostra_whatsapp_com_link(self):
        vaga = JobFactory(company=self.company)
        aluno = UserProfileFactory(phone_number="5545999990000@c.us")
        JobApplicationFactory(job=vaga, user=aluno)

        response = self._abrir()

        self.assertContains(response, "https://wa.me/5545999990000")
        self.assertContains(response, "(45) 99999-0000")
        self.assertNotContains(response, "@c.us")

    def test_painel_whatsapp_que_nao_e_telefone_nao_gera_link(self):
        vaga = JobFactory(company=self.company)
        JobApplicationFactory(job=vaga, user=UserProfileFactory(phone_number="123456789012345@lid"))

        response = self._abrir()

        self.assertNotContains(response, "wa.me")
        self.assertNotContains(response, "@lid")

    def test_painel_identifica_o_candidato_por_ra_curso_e_periodo(self):
        vaga = JobFactory(company=self.company)
        curso = Course.objects.create(name="Ciência da Computação")
        aluno = UserProfileFactory(ra="a1234567", course=curso)
        JobApplicationFactory(job=vaga, user=aluno, profile_snapshot={"periodo": "5º período"})

        response = self._abrir()

        self.assertContains(response, "RA a1234567")
        self.assertContains(response, "Ciência da Computação, 5º período")

    def test_painel_empresa_pendente_mostra_aviso_e_desabilita_publicar(self):
        self.company.status = CompanyStatus.PENDING
        self.company.save()

        response = self._abrir()

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "aguardando aprovação")
        self.assertContains(response, "Publicar nova vaga")
        self.assertNotContains(response, 'href="/empresas/vagas/nova/"')
        self.assertContains(response, "disabled")

    def test_painel_empresa_bloqueada_mostra_aviso_e_desabilita_publicar(self):
        self.company.status = CompanyStatus.BLOCKED
        self.company.save()

        response = self._abrir()

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "bloqueada")
        self.assertNotContains(response, 'href="/empresas/vagas/nova/"')

    def test_painel_empresa_sem_vagas_nem_candidaturas_mostra_estados_vazios(self):
        response = self._abrir()

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Publique a primeira vaga")
        self.assertContains(response, "Nenhuma candidatura")
        self.assertContains(response, "<strong>0</strong>", count=4)

    def test_painel_nao_mostra_vaga_removida_nem_de_outra_empresa(self):
        JobFactory(company=self.company, status=JobStatus.REMOVED, titulo="Vaga removida")
        _, outra = _usuario_com_empresa("outro", cnpj="22.333.444/0001-81")
        JobFactory(company=outra, titulo="Vaga da concorrente")

        response = self._abrir()

        self.assertNotContains(response, "Vaga removida")
        self.assertNotContains(response, "Vaga da concorrente")

    def test_painel_so_com_vagas_removidas_mostra_estado_vazio(self):
        """Vaga removida some da lista; sem vagas ativas o convite para publicar volta."""
        JobFactory(company=self.company, status=JobStatus.REMOVED, titulo="Vaga removida")

        response = self._abrir()

        self.assertNotContains(response, "Vaga removida")
        self.assertContains(response, "Publique a primeira vaga")

    def test_painel_lista_vaga_ativa_com_um_unico_editar(self):
        JobFactory(company=self.company, status=JobStatus.APPROVED, titulo="Vaga ativa")

        response = self._abrir()

        self.assertContains(response, "Vaga ativa")
        # Regressão: o botão Editar já apareceu duplicado em cada linha da lista.
        self.assertEqual(response.content.decode().count("Editar</a>"), 1)

    def test_painel_escapa_html_de_titulo_e_motivo(self):
        JobFactory(
            company=self.company,
            status=JobStatus.REJECTED,
            titulo="<script>alert(1)</script>",
            rejection_reason="<img src=x onerror=alert(2)>",
        )

        response = self._abrir()

        self.assertNotContains(response, "<script>alert(1)</script>")
        self.assertNotContains(response, "<img src=x")
        self.assertContains(response, "&lt;script&gt;alert(1)&lt;/script&gt;")

    def test_menu_marca_painel_como_ativo_e_mostra_contador(self):
        vaga = JobFactory(company=self.company)
        JobApplicationFactory(job=vaga, user=UserProfileFactory())
        JobApplicationFactory(job=vaga, user=UserProfileFactory())

        response = self._abrir()

        self.assertContains(response, '<span class="contador">2</span>')
        self.assertContains(response, 'class="ativo" aria-current="page">Painel')

    def test_menu_sem_candidaturas_novas_nao_mostra_contador(self):
        response = self._abrir()

        self.assertNotContains(response, 'class="contador"')

    def test_painel_sem_empresa_redireciona_para_criar(self):
        sem_empresa = User.objects.create_user(
            username="semempresa", email="sem@empresa.com", password="TestPass123!"
        )
        self.client.force_login(sem_empresa)

        response = self.client.get(PAINEL)

        self.assertRedirects(response, "/empresas/criar/", fetch_redirect_response=False)

    def test_painel_anonimo_redireciona_para_login(self):
        response = self.client.get(PAINEL)

        self.assertRedirects(
            response, f"/empresas/login/?next={PAINEL}", fetch_redirect_response=False
        )

    def test_login_empresa_vai_para_painel(self):
        EmailAddress.objects.create(
            user=self.user, email=self.user.email, verified=True, primary=True
        )

        response = self.client.post(
            "/empresas/login/", {"login": self.user.email, "password": "TestPass123!"}
        )

        self.assertRedirects(response, PAINEL, fetch_redirect_response=False)

    def test_painel_continua_acessivel_so_dentro_do_portal_da_empresa(self):
        """O painel não é gated por aprovação (senão pendente/bloqueada ficaria em laço)."""
        self.company.status = CompanyStatus.PENDING
        self.company.save()
        self.client.force_login(self.user)

        response = self.client.get("/empresas/vagas/nova/")

        self.assertRedirects(response, PAINEL, fetch_redirect_response=False)
        self.assertEqual(self.client.get(PAINEL).status_code, 200)


@override_settings(CACHES=CACHES_LOCMEM)
class TestDestinosDaEmpresa(TestCase):
    """Depois de criar/editar vaga ou cadastrar a empresa, o destino é o painel."""

    def setUp(self):
        self.client = Client()
        self.user, self.company = _usuario_com_empresa()
        self.client.force_login(self.user)

    def _dados_vaga(self, **extra):
        dados = {
            "titulo": "Estagiário de TI",
            "descricao": "Desenvolvimento web",
            "requisitos": "Cursando CC",
            "salario": "R$ 1.200,00",
            "tipo": "Estágio",
        }
        dados.update(extra)
        return dados

    def test_criar_vaga_leva_ao_painel(self):
        response = self.client.post("/empresas/vagas/nova/", self._dados_vaga())

        self.assertRedirects(response, PAINEL, fetch_redirect_response=False)

    def test_editar_vaga_leva_ao_painel(self):
        vaga = JobFactory(company=self.company, status=JobStatus.PENDING)

        response = self.client.post(
            f"/empresas/vagas/{vaga.pk}/editar/", self._dados_vaga(tipo=vaga.tipo)
        )

        self.assertRedirects(response, PAINEL, fetch_redirect_response=False)

    def test_remover_vaga_leva_ao_painel(self):
        vaga = JobFactory(company=self.company)

        response = self.client.post(f"/empresas/vagas/{vaga.pk}/deletar/")

        self.assertRedirects(response, PAINEL, fetch_redirect_response=False)

    def test_tela_de_criar_empresa_com_empresa_existente_leva_ao_painel(self):
        response = self.client.get("/empresas/criar/")

        self.assertRedirects(response, PAINEL, fetch_redirect_response=False)

    def test_cadastrar_empresa_leva_ao_painel(self):
        sem_empresa = User.objects.create_user(
            username="novo", email="novo@empresa.com", password="TestPass123!"
        )
        self.client.force_login(sem_empresa)

        response = self.client.post(
            "/empresas/criar/",
            {
                "cnpj": "22.333.444/0001-81",
                "nome": "Empresa Nova",
                "telefone": "(45) 3268-0000",
                "contato_nome": "Ana",
                "contato_cargo": "RH",
            },
        )

        self.assertRedirects(response, PAINEL, fetch_redirect_response=False)
        self.assertTrue(Company.objects.filter(user=sem_empresa).exists())

    def test_salvar_dados_da_empresa_continua_em_perfil(self):
        response = self.client.post(
            "/empresas/perfil/",
            {
                "nome": "Nome Novo",
                "telefone": "(45) 3268-0000",
                "endereco": "Rua A",
                "descricao": "Descrição",
                "contato_nome": "Mariana",
                "contato_cargo": "RH",
            },
        )

        self.assertRedirects(response, "/empresas/perfil/", fetch_redirect_response=False)
