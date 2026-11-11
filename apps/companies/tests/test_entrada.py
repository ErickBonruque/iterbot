"""Telas de entrada da empresa (layout dividido): login, cadastro, senha, confirmações."""

from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import Client, TestCase, override_settings

from apps.companies.tests.helpers import usuario_com_empresa
from apps.jobs.tests.factories import CompanyFactory

CACHES_LOCMEM = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}

LOGIN = "/empresas/login/"
CADASTRO = "/empresas/signup/"
TELAS_DE_ENTRADA = [
    LOGIN,
    CADASTRO,
    "/accounts/password/reset/",
    "/accounts/password/reset/done/",
    "/accounts/password/reset/key/done/",
    "/accounts/password/reset/key/1-chave-invalida/",
    "/accounts/confirm-email/",
    "/accounts/confirm-email/chave-invalida/",
]


@override_settings(CACHES=CACHES_LOCMEM)
class TestTelasDeEntrada(TestCase):
    def setUp(self):
        cache.clear()
        self.client = Client()
        patcher = patch("apps.companies.views.bot_whatsapp_url", return_value=None)
        self.bot_url = patcher.start()
        self.addCleanup(patcher.stop)

    def test_login_e_cadastro_tem_logo_utfpr(self):
        """Exigência do registro (INPI): logo oficial nas telas de entrada da empresa."""
        for url in (LOGIN, CADASTRO):
            with self.subTest(url=url):
                self.assertContains(self.client.get(url), "img/logo-utfpr.png")

    def test_todas_as_telas_de_entrada_usam_o_layout_dividido(self):
        for url in TELAS_DE_ENTRADA:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, 'class="entrada"')
                self.assertContains(response, "css/portal.css")
                self.assertContains(response, "img/logo-utfpr.png", count=1)

    def test_telas_de_entrada_sem_estilo_inline_nem_emoji(self):
        for url in TELAS_DE_ENTRADA:
            with self.subTest(url=url):
                html = self.client.get(url).content.decode()
                self.assertNotIn('style="', html)
                self.assertNotIn("<style", html)
                self.assertNotIn("✅", html)

    def test_login_tem_linha_para_aluno_com_link_do_bot(self):
        self.bot_url.return_value = "https://wa.me/554598482007"

        response = self.client.get(LOGIN)

        self.assertContains(response, "É aluno da UTFPR?")
        self.assertContains(response, 'href="https://wa.me/554598482007"')

    def test_login_sem_numero_do_bot_mostra_so_o_texto(self):
        response = self.client.get(LOGIN)

        self.assertContains(response, "É aluno da UTFPR?")
        self.assertNotContains(response, "wa.me")

    def test_login_mostra_titulo_e_links_do_portal(self):
        response = self.client.get(LOGIN)

        self.assertContains(response, "Entrar no portal")
        self.assertContains(response, 'href="/accounts/password/reset/"')
        self.assertContains(response, f'href="{CADASTRO}"')
        self.assertContains(response, "Manter conectado")

    def test_login_com_senha_errada_mostra_o_alerta_e_mantem_o_email(self):
        user, _ = usuario_com_empresa()

        response = self.client.post(LOGIN, {"login": user.email, "password": "errada"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "alert-danger")
        self.assertContains(response, user.email)

    def test_cadastro_agrupa_os_campos_em_empresa_responsavel_e_acesso(self):
        html = self.client.get(CADASTRO).content.decode()

        posicoes = [
            html.index(f">{grupo}</legend>") for grupo in ("Empresa", "Responsável", "Acesso")
        ]
        self.assertEqual(posicoes, sorted(posicoes))
        for campo in (
            "cnpj",
            "nome",
            "telefone",
            "contato_nome",
            "contato_cargo",
            "email",
            "password1",
            "password2",
        ):
            self.assertIn(f'name="{campo}"', html)

    def test_cadastro_mostra_requisitos_de_senha(self):
        self.assertContains(self.client.get(CADASTRO), "mínimo de 8 caracteres")

    def test_cadastro_com_cnpj_repetido_mostra_o_erro_no_campo(self):
        CompanyFactory(cnpj="11.222.333/0001-81")

        response = self.client.post(
            CADASTRO,
            {
                "cnpj": "11.222.333/0001-81",
                "nome": "Outra",
                "email": "rh@outra.com.br",
                "telefone": "(45) 3268-0000",
                "contato_nome": "Ana",
                "contato_cargo": "RH",
                "password1": "SenhaForte#2026",
                "password2": "SenhaForte#2026",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "is-invalid")
        self.assertContains(response, "Já existe uma empresa cadastrada com este CNPJ.")

    def test_fluxo_de_senha_volta_para_o_login_da_empresa(self):
        for url in (
            "/accounts/password/reset/",
            "/accounts/password/reset/done/",
            "/accounts/password/reset/key/done/",
        ):
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertContains(response, f'href="{LOGIN}"')
                self.assertNotContains(response, "/accounts/login/")

    def test_pedido_de_nova_senha_pede_o_email_da_empresa(self):
        response = self.client.get("/accounts/password/reset/")

        self.assertContains(response, "Recuperar senha")
        self.assertContains(response, 'name="email"')
        self.assertNotContains(response, "alunos.utfpr.edu.br")

    def test_link_de_redefinicao_invalido_oferece_pedir_outro(self):
        response = self.client.get("/accounts/password/reset/key/1-chave-invalida/")

        self.assertContains(response, "Link inválido ou expirado")
        self.assertContains(response, 'href="/accounts/password/reset/"')

    def test_confirmacao_de_email_invalida_leva_ao_cadastro_da_empresa(self):
        response = self.client.get("/accounts/confirm-email/chave-invalida/")

        self.assertContains(response, "Link inválido ou expirado")
        self.assertContains(response, f'href="{CADASTRO}"')
        self.assertNotContains(response, "/accounts/signup/")

    def test_verificacao_enviada_mostra_o_email_da_sessao(self):
        session = self.client.session
        session["pending_verification_email"] = "rh@empresa.com.br"
        session.save()

        response = self.client.get("/accounts/confirm-email/")

        self.assertContains(response, "Verifique seu e-mail")
        self.assertContains(response, "rh@empresa.com.br")

    def test_verificacao_enviada_sem_email_na_sessao_usa_texto_generico(self):
        response = self.client.get("/accounts/confirm-email/")

        self.assertContains(response, "e-mail informado no cadastro")

    def test_logout_pede_confirmacao_no_layout_de_entrada(self):
        user = User.objects.create_user(username="sair", email="sair@empresa.com", password="x")
        self.client.force_login(user)

        response = self.client.get("/empresas/logout/")

        self.assertContains(response, "Tem certeza")
        self.assertContains(response, 'class="entrada"')
        self.assertContains(response, 'href="/empresas/painel/"')
