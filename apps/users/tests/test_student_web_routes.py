"""Aluno não tem login/cadastro web com senha: usa o WhatsApp. Telas que ele ainda vê."""

from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.jobs.tests.factories import CompanyFactory

CACHES_LOCMEM = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}

SENHA = "TesteSenha123!"
EMAIL_ALUNO = "aluno@alunos.utfpr.edu.br"
LINK_DO_BOT = "https://wa.me/554598482007"


@override_settings(CACHES=CACHES_LOCMEM)
class TestLoginECadastroDeAlunoSairam(TestCase):
    def setUp(self):
        cache.clear()

    def test_accounts_login_redireciona(self):
        for metodo in (self.client.get, self.client.post):
            with self.subTest(metodo=metodo.__name__):
                response = metodo("/accounts/login/")
                self.assertRedirects(response, "/empresas/login/", fetch_redirect_response=False)

    def test_accounts_login_preserva_o_next(self):
        response = self.client.get("/accounts/login/?next=/empresas/painel/")

        self.assertRedirects(
            response, "/empresas/login/?next=/empresas/painel/", fetch_redirect_response=False
        )

    def test_accounts_login_nao_autentica_nem_com_senha_certa(self):
        user = User.objects.create_user(username=EMAIL_ALUNO, email=EMAIL_ALUNO, password=SENHA)
        user.emailaddress_set.create(email=EMAIL_ALUNO, verified=True, primary=True)

        self.client.post("/accounts/login/", {"login": EMAIL_ALUNO, "password": SENHA})

        self.assertNotIn("_auth_user_id", self.client.session)

    def test_accounts_signup_redireciona(self):
        for metodo in (self.client.get, self.client.post):
            with self.subTest(metodo=metodo.__name__):
                response = metodo("/accounts/signup/")
                self.assertRedirects(response, "/empresas/signup/", fetch_redirect_response=False)

    def test_accounts_signup_post_nao_cria_usuario(self):
        self.client.post(
            "/accounts/signup/",
            {"email": EMAIL_ALUNO, "password1": SENHA, "password2": SENHA},
        )

        self.assertFalse(User.objects.filter(email=EMAIL_ALUNO).exists())

    def test_nomes_das_rotas_continuam_resolvendo_para_o_allauth(self):
        """O allauth faz reverse("account_login") por dentro; o nome precisa existir."""
        self.assertEqual(reverse("account_login"), "/accounts/login/")
        self.assertEqual(reverse("account_signup"), "/accounts/signup/")

    def test_logout_vai_para_login_da_empresa(self):
        for i, url in enumerate(("/accounts/logout/", "/empresas/logout/")):
            with self.subTest(url=url):
                user = User.objects.create_user(
                    username=f"sai{i}", email=f"sai{i}@empresa.com", password=SENHA
                )
                self.client.force_login(user)

                response = self.client.post(url)

                self.assertRedirects(response, "/empresas/login/", fetch_redirect_response=False)
                self.assertNotIn("_auth_user_id", self.client.session)


@override_settings(CACHES=CACHES_LOCMEM)
class TestTelasDoAluno(TestCase):
    def setUp(self):
        cache.clear()
        self.aluno = User.objects.create_user(
            username=EMAIL_ALUNO, email=EMAIL_ALUNO, password=SENHA
        )

    def _sucesso(self, bot_url=LINK_DO_BOT):
        with patch("apps.users.views.bot_whatsapp_url", return_value=bot_url):
            return self.client.get("/accounts/success/")

    def test_sucesso_aluno_sem_emoji_e_com_whatsapp(self):
        self.client.force_login(self.aluno)

        response = self._sucesso()

        self.assertContains(response, "Voltar para o WhatsApp")
        self.assertContains(response, f'href="{LINK_DO_BOT}"')
        self.assertContains(response, EMAIL_ALUNO)
        self.assertNotContains(response, "🐧")
        self.assertContains(response, 'class="simples"')

    def test_sucesso_aluno_sem_numero_do_bot_nao_inventa_link(self):
        self.client.force_login(self.aluno)

        response = self._sucesso(bot_url=None)

        self.assertNotContains(response, "wa.me")
        self.assertContains(response, "conversa com o IterBot no WhatsApp")

    def test_sucesso_anonimo_leva_ao_login_da_empresa(self):
        response = self._sucesso()

        self.assertContains(response, 'href="/empresas/login/"')
        self.assertNotContains(response, "/accounts/login/")
        self.assertNotContains(response, "Voltar para o WhatsApp")

    def test_sucesso_com_empresa_leva_ao_painel(self):
        CompanyFactory(user=self.aluno)
        self.client.force_login(self.aluno)

        response = self._sucesso()

        self.assertContains(response, 'href="/empresas/painel/"')
        self.assertNotContains(response, "Voltar para o WhatsApp")

    def test_link_invalido_mostra_proximo_passo(self):
        with patch("apps.users.views.bot_whatsapp_url", return_value=LINK_DO_BOT):
            response = self.client.get("/confirmar-email/token-invalido/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Link expirado ou inválido")
        self.assertContains(response, "Abrir o WhatsApp")
        self.assertContains(response, f'href="{LINK_DO_BOT}"')
        self.assertNotContains(response, "/accounts/login/")

    def test_link_invalido_sem_numero_do_bot_ainda_diz_o_que_fazer(self):
        with patch("apps.users.views.bot_whatsapp_url", return_value=None):
            response = self.client.get("/confirmar-email/token-invalido/")

        self.assertContains(response, "pelo WhatsApp")
        self.assertNotContains(response, "wa.me")

    def test_vinculo_de_empresa_invalido_mostra_proximo_passo(self):
        with patch("apps.users.views.bot_whatsapp_url", return_value=LINK_DO_BOT):
            response = self.client.get("/accounts/confirmar-empresa/token-invalido/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Link expirado ou inválido")
        self.assertContains(response, f'href="{LINK_DO_BOT}"')

    def test_telas_do_aluno_sem_emoji_nem_estilo_inline(self):
        self.client.force_login(self.aluno)
        paginas = [
            self._sucesso(),
            self.client.get("/confirmar-email/token-invalido/"),
        ]
        for response in paginas:
            html = response.content.decode()
            self.assertNotIn('style="', html)
            self.assertNotIn("<style", html)
            for emoji in ("🐧", "✅", "❌"):
                self.assertNotIn(emoji, html)
