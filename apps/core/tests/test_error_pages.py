"""Páginas de erro 403, 404 e 500 no layout do portal (com DEBUG desligado)."""

from unittest.mock import patch

from django.contrib.auth.models import User
from django.template.loader import render_to_string
from django.test import Client, TestCase, override_settings

from apps.companies.tests.helpers import usuario_com_empresa
from apps.jobs.tests.factories import JobFactory

CACHES_LOCMEM = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}


@override_settings(DEBUG=False, CACHES=CACHES_LOCMEM)
class TestPaginasDeErro(TestCase):
    def setUp(self):
        self.client = Client(raise_request_exception=False)

    def _vaga_de_outra_empresa(self):
        _, outra = usuario_com_empresa("outra", cnpj="22.333.444/0001-81")
        return JobFactory(company=outra)

    def test_404_personalizado(self):
        response = self.client.get("/nao-existe/")

        self.assertContains(response, "Página não encontrada", status_code=404)
        self.assertContains(response, "img/mascote.png", status_code=404)
        self.assertContains(response, 'class="simples"', status_code=404)

    def test_404_de_vaga_inexistente_nao_vaza_a_mensagem_da_excecao(self):
        response = self.client.get("/vagas/999999/")

        self.assertContains(response, "Página não encontrada", status_code=404)
        self.assertNotContains(response, "No Job matches", status_code=404)

    def test_403_personalizado(self):
        user, _ = usuario_com_empresa()
        vaga = self._vaga_de_outra_empresa()
        self.client.force_login(user)

        response = self.client.get(f"/empresas/vagas/{vaga.pk}/editar/")

        self.assertContains(response, "Acesso negado", status_code=403)
        self.assertContains(response, "img/mascote.png", status_code=403)
        self.assertContains(response, 'href="/empresas/painel/"', status_code=403)

    def test_403_nao_mostra_a_mensagem_interna_da_excecao(self):
        sem_empresa = User.objects.create_user(
            username="semempresa", email="sem@empresa.com", password="TestPass123!"
        )
        self.client.force_login(sem_empresa)

        response = self.client.get("/empresas/candidaturas/")

        self.assertContains(response, "Acesso negado", status_code=403)
        self.assertNotContains(response, "não possui empresa vinculada", status_code=403)

    def test_500_renderiza_sem_contexto(self):
        html = render_to_string("500.html")

        self.assertIn("Algo deu errado", html)
        self.assertIn("img/mascote.png", html)
        self.assertNotIn("{{", html)
        self.assertNotIn("{%", html)

    def test_500_de_verdade_usa_a_pagina_personalizada(self):
        user, _ = usuario_com_empresa()
        self.client.force_login(user)

        with patch(
            "apps.companies.views.CompaniesService.dashboard_summary",
            side_effect=RuntimeError("segredo interno"),
        ):
            response = self.client.get("/empresas/painel/")

        self.assertContains(response, "Algo deu errado", status_code=500)
        self.assertNotContains(response, "segredo interno", status_code=500)
        self.assertNotContains(response, "Traceback", status_code=500)

    def test_paginas_de_erro_sem_estilo_inline_nem_emoji(self):
        user, _ = usuario_com_empresa()
        vaga = self._vaga_de_outra_empresa()
        self.client.force_login(user)
        paginas = [
            self.client.get("/nao-existe/"),
            self.client.get(f"/empresas/vagas/{vaga.pk}/editar/"),
        ]
        html = [p.content.decode() for p in paginas] + [render_to_string("500.html")]

        for pagina in html:
            self.assertNotIn('style="', pagina)
            self.assertNotIn("<style", pagina)
            for emoji in ("🐧", "✅", "❌", "⚠"):
                self.assertNotIn(emoji, pagina)
