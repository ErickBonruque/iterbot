from types import SimpleNamespace
from unittest.mock import ANY, patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse


class AuthFlowTestCase(TestCase):
    """
    Testes de integração do que sobrou do fluxo allauth: logout e recuperação de senha.

    Login e cadastro web com senha saíram (aluno usa o WhatsApp; ver
    ``test_student_web_routes.py``); as empresas seguem usando reset de senha.
    """

    def setUp(self):
        self.valid_email = "teste@alunos.utfpr.edu.br"
        self.invalid_email = "teste@gmail.com"
        self.password = "TesteSenha123!"

    def test_logout(self):
        user = User.objects.create_user(
            username=self.valid_email, email=self.valid_email, password=self.password
        )
        self.client.force_login(user)

        response = self.client.post(reverse("account_logout"))

        self.assertEqual(response.status_code, 302)
        self.assertFalse("_auth_user_id" in self.client.session)

    def test_password_reset_flow(self):
        user = User.objects.create_user(
            username=self.valid_email, email=self.valid_email, password=self.password
        )
        user.emailaddress_set.create(email=self.valid_email, verified=True, primary=True)

        with (
            patch(
                "apps.users.adapters.DefaultAccountAdapter.render_mail",
                return_value=SimpleNamespace(subject="Reset subject", body="Reset body"),
            ),
            patch(
                "apps.users.adapters.build_email_idempotency_key",
                return_value="reset-idempotency-key",
            ) as key_spy,
            patch(
                "apps.users.adapters.send_transactional_email",
                return_value={"status": "sent"},
            ) as send_spy,
        ):
            response = self.client.post(
                reverse("account_reset_password"),
                {"email": self.valid_email},
            )

        self.assertEqual(response.status_code, 302)
        key_spy.assert_called_once_with(
            "password_reset",
            recipient=self.valid_email,
            event_token=ANY,
            event_uid=ANY,
        )
        send_spy.assert_called_once_with(
            subject="Reset subject",
            message="Reset body",
            recipient_list=[self.valid_email],
            idempotency_key="reset-idempotency-key",
            event_type="password_reset",
        )

    def test_password_reset_unknown_email_keeps_generic_response(self):
        # allauth envia um e-mail "unknown account" como hint anti-enumeracao;
        # aceitamos que o sender transacional seja chamado, mas a resposta
        # HTTP deve continuar generica (302 para a tela padrao).
        with patch(
            "apps.users.adapters.send_transactional_email",
            return_value={"status": "sent", "provider": "brevo"},
        ):
            response = self.client.post(
                reverse("account_reset_password"),
                {"email": "missing@alunos.utfpr.edu.br"},
            )

        self.assertEqual(response.status_code, 302)
        self.assertRedirects(
            response,
            reverse("account_reset_password_done"),
            fetch_redirect_response=False,
        )
