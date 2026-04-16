from django.contrib.auth.models import User
from django.core import mail
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
        """
        Registro com @alunos.utfpr.edu.br cria User e UserProfile.
        """
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

        profile = user.profile
        self.assertEqual(profile.email, self.valid_email)

    def test_signup_with_invalid_email(self):
        """
        Registro com @gmail.com é rejeitado.
        """
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
        """
        E-mail de confirmação é enviado após registro.
        """
        self.client.post(
            reverse("account_signup"),
            {
                "email": self.valid_email,
                "password1": self.password,
                "password2": self.password,
            },
        )

        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("Confirme seu cadastro", mail.outbox[0].subject)
        self.assertIn(self.valid_email, mail.outbox[0].to)

    def test_login_success(self):
        """
        Login com credenciais válidas redireciona corretamente.
        """
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
        """
        Login com e-mail não confirmado redireciona para confirmação.
        """
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
        """
        Logout limpa sessão.
        """
        user = User.objects.create_user(
            username=self.valid_email, email=self.valid_email, password=self.password
        )
        self.client.force_login(user)

        response = self.client.post(reverse("account_logout"))

        self.assertEqual(response.status_code, 302)
        self.assertFalse("_auth_user_id" in self.client.session)

    def test_password_reset_flow(self):
        """
        Recuperação de senha envia e-mail.
        """
        User.objects.create_user(
            username=self.valid_email, email=self.valid_email, password=self.password
        )

        response = self.client.post(reverse("account_reset_password"), {"email": self.valid_email})

        self.assertEqual(response.status_code, 302)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(self.valid_email, mail.outbox[0].to)
