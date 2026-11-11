"""Destino depois de confirmar o e-mail pelo link do allauth."""

from django.contrib.auth.models import AnonymousUser, User
from django.test import RequestFactory, TestCase

from apps.jobs.tests.factories import CompanyFactory
from apps.users.adapters import UTFPRAccountAdapter


class EmailConfirmationRedirectTests(TestCase):
    def _request(self, user):
        request = RequestFactory().get("/confirmar-email/token/")
        request.user = user
        request.session = {}
        return request

    def test_empresa_vai_para_o_painel(self):
        user = User.objects.create_user(
            username="empresa", email="rh@empresa.com", password="TestPass123!"
        )
        CompanyFactory(user=user)

        url = UTFPRAccountAdapter().get_email_confirmation_redirect_url(self._request(user))

        self.assertEqual(url, "/empresas/painel/")

    def test_quem_nao_tem_empresa_segue_o_padrao_do_allauth(self):
        user = User.objects.create_user(
            username="aluno", email="aluno@alunos.utfpr.edu.br", password="TestPass123!"
        )

        url = UTFPRAccountAdapter().get_email_confirmation_redirect_url(self._request(user))

        self.assertNotIn("/empresas/", url)

    def test_anonimo_segue_o_padrao_do_allauth(self):
        url = UTFPRAccountAdapter().get_email_confirmation_redirect_url(
            self._request(AnonymousUser())
        )

        self.assertNotIn("/empresas/", url)
