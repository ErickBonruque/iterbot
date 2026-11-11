"""Páginas logadas da empresa no layout do portal: formulário de vaga, dados, remoção."""

import re

from django.test import Client, TestCase, override_settings

from apps.companies.tests.helpers import usuario_com_empresa
from apps.courses.models import Area
from apps.jobs.models import JobStatus
from apps.jobs.tests.factories import JobFactory

CACHES_LOCMEM = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}


@override_settings(CACHES=CACHES_LOCMEM)
class TestJobFormPage(TestCase):
    def setUp(self):
        self.client = Client()
        self.user, self.company = usuario_com_empresa()
        self.client.force_login(self.user)

    def _editar(self, status, **campos):
        vaga = JobFactory(company=self.company, status=status, **campos)
        return vaga, self.client.get(f"/empresas/vagas/{vaga.pk}/editar/")

    def test_form_vaga_tipo_e_select(self):
        response = self.client.get("/empresas/vagas/nova/")

        select = re.search(r'<select[^>]*id="id_tipo"[^>]*>', response.content.decode())
        self.assertIsNotNone(select)
        self.assertIn("form-select", select.group(0))
        self.assertNotIn("form-control", select.group(0))
        for rotulo in ["Estágio", "CLT", "PJ", "Temporário"]:
            self.assertContains(response, f'<option value="{rotulo}">{rotulo}</option>')

    def test_form_nova_vaga_tipo_comeca_sem_selecao(self):
        response = self.client.get("/empresas/vagas/nova/")

        self.assertContains(response, '<option value="" selected>Selecione o tipo</option>')

    def test_form_nova_vaga_avisa_da_analise_e_oferece_enviar(self):
        response = self.client.get("/empresas/vagas/nova/")

        self.assertContains(response, "analisada pela UTFPR")
        self.assertContains(response, "Enviar para análise")
        self.assertContains(response, "Cancelar")
        self.assertContains(response, 'href="/empresas/painel/"')
        self.assertContains(response, "css/portal.css")

    def test_form_edicao_avisa_volta_para_analise(self):
        _, response = self._editar(JobStatus.APPROVED)

        self.assertContains(response, "volta para análise")
        self.assertContains(response, "Salvar e reenviar")

    def test_form_edicao_pendente_nao_fala_em_voltar_para_analise(self):
        _, response = self._editar(JobStatus.PENDING)

        self.assertNotContains(response, "volta para análise")
        self.assertContains(response, "Salvar alterações")

    def test_form_edicao_de_recusada_mostra_o_motivo_e_oferece_reenviar(self):
        _, response = self._editar(
            JobStatus.REJECTED, rejection_reason="Vaga fora do escopo de estágio."
        )

        self.assertContains(response, "Vaga fora do escopo de estágio.")
        self.assertContains(response, "Salvar e reenviar")

    def test_form_edicao_mostra_o_tipo_atual_selecionado(self):
        _, response = self._editar(JobStatus.PENDING, tipo="CLT")

        self.assertContains(response, '<option value="CLT" selected>CLT</option>')

    def test_form_mostra_erro_de_campo(self):
        response = self.client.post("/empresas/vagas/nova/", {"titulo": "", "tipo": "CLT"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "is-invalid")
        self.assertContains(response, "invalid-feedback")

    def test_form_areas_em_grade_com_checkbox_do_bootstrap(self):
        Area.objects.create(name="Área Grade")

        response = self.client.get("/empresas/vagas/nova/")

        self.assertContains(response, "areas-grade")
        self.assertContains(response, "form-check-input")
        self.assertContains(response, "Área Grade")

    def test_form_escapa_html_do_titulo_ao_reexibir(self):
        response = self.client.post(
            "/empresas/vagas/nova/", {"titulo": '"><script>alert(1)</script>', "tipo": ""}
        )

        self.assertNotContains(response, "<script>alert(1)</script>")


@override_settings(CACHES=CACHES_LOCMEM)
class TestCompanyProfilePage(TestCase):
    def setUp(self):
        self.client = Client()
        self.user, self.company = usuario_com_empresa()
        self.client.force_login(self.user)

    def test_perfil_mostra_cnpj_e_formulario_de_dados(self):
        response = self.client.get("/empresas/perfil/")

        self.assertContains(response, self.company.cnpj)
        self.assertContains(response, "Dados da empresa")
        self.assertContains(response, 'name="telefone"')
        self.assertContains(response, 'class="ativo" aria-current="page">Dados da empresa')

    def test_perfil_nao_lista_vagas(self):
        JobFactory(company=self.company, titulo="Vaga que fica no painel")

        response = self.client.get("/empresas/perfil/")

        self.assertNotContains(response, "Vaga que fica no painel")
        self.assertNotContains(response, "Minhas vagas")

    def test_perfil_mostra_erro_de_campo(self):
        response = self.client.post("/empresas/perfil/", {"nome": "", "telefone": ""})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "is-invalid")


@override_settings(CACHES=CACHES_LOCMEM)
class TestJobDeletePage(TestCase):
    def test_confirmar_remocao_tem_botao_destrutivo_e_cancelar_volta_ao_painel(self):
        user, company = usuario_com_empresa()
        vaga = JobFactory(company=company, titulo="Vaga a remover")
        client = Client()
        client.force_login(user)

        response = client.get(f"/empresas/vagas/{vaga.pk}/deletar/")

        self.assertContains(response, "Vaga a remover")
        self.assertContains(response, "btn-danger")
        self.assertContains(response, "Confirmar remoção")
        self.assertContains(response, 'href="/empresas/painel/"')


@override_settings(CACHES=CACHES_LOCMEM)
class TestCompanyCreatePage(TestCase):
    def test_criar_empresa_usa_o_layout_do_portal(self):
        from django.contrib.auth.models import User

        sem_empresa = User.objects.create_user(
            username="novo", email="novo@empresa.com", password="TestPass123!"
        )
        client = Client()
        client.force_login(sem_empresa)

        response = client.get("/empresas/criar/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Cadastrar empresa")
        self.assertContains(response, "css/portal.css")
        self.assertContains(response, 'name="cnpj"')

    def test_criar_empresa_mostra_erro_de_cnpj_invalido(self):
        from django.contrib.auth.models import User

        sem_empresa = User.objects.create_user(
            username="novo2", email="novo2@empresa.com", password="TestPass123!"
        )
        client = Client()
        client.force_login(sem_empresa)

        response = client.post(
            "/empresas/criar/",
            {
                "cnpj": "123",
                "nome": "X",
                "telefone": "1",
                "contato_nome": "Y",
                "contato_cargo": "Z",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "is-invalid")


@override_settings(CACHES=CACHES_LOCMEM)
class TestPaginasSemEstiloInline(TestCase):
    """Todo estilo mora em static/css/portal.css (restrição global da reforma)."""

    def test_paginas_logadas_da_empresa_nao_tem_style_inline(self):
        user, company = usuario_com_empresa()
        vaga = JobFactory(company=company)
        client = Client()
        client.force_login(user)
        urls = [
            "/empresas/painel/",
            "/empresas/perfil/",
            "/empresas/candidaturas/",
            "/empresas/vagas/nova/",
            f"/empresas/vagas/{vaga.pk}/editar/",
            f"/empresas/vagas/{vaga.pk}/deletar/",
        ]
        for url in urls:
            with self.subTest(url=url):
                html = client.get(url).content.decode()
                self.assertNotIn('style="', html)
                self.assertNotIn("<style", html)
