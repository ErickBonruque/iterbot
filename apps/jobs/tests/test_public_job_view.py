"""Página pública de vaga: /vagas/<id>/ (sem login, só vagas aprovadas)."""

from unittest.mock import patch
from urllib.parse import urlsplit

from django.test import Client, TestCase

from apps.courses.models import Area
from apps.jobs.models import JobStatus
from apps.jobs.services import _serialize_local_job
from apps.jobs.tests.factories import CompanyFactory, JobFactory

LINK_DO_BOT = "https://wa.me/554598482007"


class TestJobPublicDetailView(TestCase):
    def setUp(self):
        self.client = Client()
        self.company = CompanyFactory(
            nome="Cooperativa Oeste",
            endereco="Av. Brasil, 1000 - Santa Helena/PR",
            email="rh@cooperativa.com.br",
            telefone="(45) 3268-0000",
            contato_nome="Mariana Souza",
            cnpj="11.222.333/0001-81",
        )
        self.job = JobFactory(
            company=self.company,
            titulo="Estágio em Desenvolvimento de Software",
            descricao="Apoio no desenvolvimento de sistemas.\nTrabalho em Django.",
            requisitos="Cursando Ciência da Computação.",
            salario="R$ 1.200,00",
            tipo="Estágio",
        )

    def _abrir(self, pk=None, bot_url=None):
        with patch("apps.jobs.views.bot_whatsapp_url", return_value=bot_url):
            return self.client.get(f"/vagas/{pk or self.job.pk}/")

    def test_vaga_aprovada_200(self):
        response = self._abrir()

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Estágio em Desenvolvimento de Software")
        self.assertContains(response, "Cooperativa Oeste")
        self.assertContains(response, "Apoio no desenvolvimento de sistemas.")
        self.assertContains(response, "Cursando Ciência da Computação.")
        self.assertContains(response, "R$ 1.200,00")
        self.assertContains(response, "Av. Brasil, 1000 - Santa Helena/PR")
        self.assertContains(response, "Vagas do meu curso")
        self.assertContains(response, 'class="simples"')

    def test_nao_exige_login(self):
        self.assertEqual(Client().get(f"/vagas/{self.job.pk}/").status_code, 200)

    def test_vaga_nao_aprovada_404(self):
        for status in (
            JobStatus.PENDING,
            JobStatus.REJECTED,
            JobStatus.REMOVED,
            JobStatus.EXPIRED,
            JobStatus.DRAFT,
        ):
            with self.subTest(status=status):
                vaga = JobFactory(company=self.company, status=status, titulo=f"Segredo {status}")

                response = self._abrir(vaga.pk)

                self.assertEqual(response.status_code, 404)
                self.assertNotContains(response, f"Segredo {status}", status_code=404)

    def test_vaga_inexistente_404(self):
        self.assertEqual(self._abrir(999999).status_code, 404)

    def test_aceita_so_get(self):
        self.assertEqual(self.client.post(f"/vagas/{self.job.pk}/").status_code, 405)

    def test_titulo_com_html_escapado(self):
        vaga = JobFactory(
            company=self.company,
            titulo="<b>x</b><script>alert(1)</script>",
            descricao="<img src=x onerror=alert(2)>",
        )

        response = self._abrir(vaga.pk)

        self.assertContains(response, "&lt;b&gt;x&lt;/b&gt;")
        self.assertNotContains(response, "<script>alert(1)</script>")
        self.assertNotContains(response, "<img src=x")

    def test_nao_expoe_dados_pessoais_nem_de_contato(self):
        response = self._abrir()

        for dado in (
            "rh@cooperativa.com.br",
            "(45) 3268-0000",
            "Mariana Souza",
            "11.222.333/0001-81",
        ):
            with self.subTest(dado=dado):
                self.assertNotContains(response, dado)

    def test_lista_as_areas_da_vaga(self):
        self.job.areas.set(
            [Area.objects.create(name="Tecnologia X"), Area.objects.create(name="Gestão X")]
        )

        response = self._abrir()

        self.assertContains(response, "Tecnologia X")
        self.assertContains(response, "Gestão X")

    def test_vaga_sem_areas_diz_que_serve_para_todas(self):
        self.assertContains(self._abrir(), "Todas as áreas")

    def test_botao_do_whatsapp_leva_ao_numero_do_bot(self):
        response = self._abrir(bot_url=LINK_DO_BOT)

        self.assertContains(response, "Abrir o IterBot no WhatsApp")
        self.assertContains(response, f'href="{LINK_DO_BOT}"')

    def test_sem_numero_do_bot_nao_inventa_link_mas_mantem_a_instrucao(self):
        response = self._abrir(bot_url=None)

        self.assertNotContains(response, "wa.me")
        self.assertNotContains(response, "Abrir o IterBot no WhatsApp")
        self.assertContains(response, "Vagas do meu curso")

    def test_sem_estilo_inline(self):
        html = self._abrir(bot_url=LINK_DO_BOT).content.decode()

        self.assertNotIn('style="', html)
        self.assertNotIn("<style", html)

    def test_link_do_resumo_semanal_abre_a_pagina(self):
        """O link que o resumo semanal manda no WhatsApp tem que existir."""
        with self.settings(PORTAL_BASE_URL="https://portal.example"):
            url = _serialize_local_job(self.job)["job_url"]

        response = self._abrir(pk=urlsplit(url).path.strip("/").split("/")[-1])

        self.assertEqual(urlsplit(url).path, f"/vagas/{self.job.pk}/")
        self.assertEqual(response.status_code, 200)
