from types import SimpleNamespace
from unittest.mock import ANY, patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from apps.users.models import UserProfile


class AuthFlowTestCase(TestCase):
    """
    Testes de integração do fluxo de autenticação de alunos.
    """

    def setUp(self):
        self.valid_email = "teste@alunos.utfpr.edu.br"
        self.invalid_email = "teste@gmail.com"
        self.password = "TesteSenha123!"

    def test_signup_with_valid_email(self):
        response = self.client.post(
            reverse("account_signup"),
            {
                "email": self.valid_email,
                "password1": self.password,
                "password2": self.password,
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(User.objects.filter(email=self.valid_email).exists())

        user = User.objects.get(email=self.valid_email)
        self.assertTrue(UserProfile.objects.filter(user=user).exists())
        self.assertEqual(user.profile.email, self.valid_email)

    def test_signup_with_invalid_email(self):
        response = self.client.post(
            reverse("account_signup"),
            {
                "email": self.invalid_email,
                "password1": self.password,
                "password2": self.password,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(email=self.invalid_email).exists())
        self.assertContains(response, "Apenas e-mails @alunos.utfpr.edu.br são aceitos")

    def test_email_confirmation_sent(self):
        # O UTFPRAccountAdapter roteia todos os emails allauth via
        # send_transactional_email (Brevo/Resend/SES), entao o outbox Django
        # nao e mais populado. Verificamos a chamada ao sender transacional.
        with patch(
            "apps.users.adapters.send_transactional_email",
            return_value={"status": "sent", "provider": "brevo"},
        ) as send_spy:
            self.client.post(
                reverse("account_signup"),
                {
                    "email": self.valid_email,
                    "password1": self.password,
                    "password2": self.password,
                },
            )

        send_spy.assert_called_once()
        call_kwargs = send_spy.call_args.kwargs
        self.assertIn("Confirme seu cadastro", call_kwargs["subject"])
        self.assertEqual(call_kwargs["recipient_list"], [self.valid_email])
        self.assertEqual(call_kwargs["event_type"], "email_confirmation")

    def test_login_success(self):
        user = User.objects.create_user(
            username=self.valid_email, email=self.valid_email, password=self.password
        )
        user.emailaddress_set.create(email=self.valid_email, verified=True, primary=True)

        response = self.client.post(
            reverse("account_login"),
            {"login": self.valid_email, "password": self.password},
        )

        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, "/accounts/success/")

    def test_login_unverified_email(self):
        User.objects.create_user(
            username=self.valid_email, email=self.valid_email, password=self.password
        )

        response = self.client.post(
            reverse("account_login"),
            {"login": self.valid_email, "password": self.password},
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("confirm-email", response.request["PATH_INFO"])

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
