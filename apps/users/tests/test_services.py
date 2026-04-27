"""Testes do UTFPRAuthService — fluxo de link_user e logout no bot.

Garante que:
- Usuário novo passa pelo fluxo completo de verificação por e-mail.
- Usuário previamente verificado faz re-login direto, sem novo token/e-mail.
- Logout preserva o vínculo verificado para permitir re-login sem reenvio.
"""

from django.test import TestCase

from apps.users.models import UserProfile
from apps.users.services import UTFPRAuthService


class _StubDispatcher:
    def __init__(self) -> None:
        self.calls: list[int] = []

    def dispatch_confirmation_email(self, user_id: int) -> None:
        self.calls.append(user_id)


class LinkUserTests(TestCase):
    def setUp(self):
        self.dispatcher = _StubDispatcher()
        self.service = UTFPRAuthService(email_dispatcher=self.dispatcher)
        self.phone = "5599999999999@c.us"
        self.email = "aluno@alunos.utfpr.edu.br"

    def test_first_signup_generates_token_and_keeps_unverified(self):
        user = self.service.link_user(self.phone, "a1234567", "senha", self.email)

        self.assertIsNotNone(user)
        self.assertFalse(user.is_authenticated_utfpr)
        self.assertFalse(user.email_verified)
        self.assertIsNotNone(user.email_confirmation_token)

    def test_relogin_after_verification_skips_token_regeneration(self):
        # Primeiro cadastro
        user = self.service.link_user(self.phone, "a1234567", "senha", self.email)
        original_token = user.email_confirmation_token

        # Simula confirmação manual do e-mail
        user.is_authenticated_utfpr = True
        user.email_verified = True
        user.save()

        # Aluno desloga
        self.service.logout(self.phone)
        user.refresh_from_db()
        self.assertFalse(user.is_authenticated_utfpr)
        # Logout deve preservar dados de identidade
        self.assertEqual(user.email, self.email)
        self.assertTrue(user.email_verified)

        # Aluno tenta logar de novo com mesmo e-mail
        relogged = self.service.link_user(self.phone, "a1234567", "senha", self.email)

        self.assertIsNotNone(relogged)
        self.assertTrue(relogged.is_authenticated_utfpr)
        self.assertTrue(relogged.email_verified)
        # Token NÃO deve ter sido regenerado
        self.assertEqual(relogged.email_confirmation_token, original_token)

    def test_relogin_with_different_email_triggers_new_verification(self):
        user = self.service.link_user(self.phone, "a1234567", "senha", self.email)
        user.is_authenticated_utfpr = True
        user.email_verified = True
        user.save()

        new_email = "outro@alunos.utfpr.edu.br"
        result = self.service.link_user(self.phone, "a1234567", "senha", new_email)

        self.assertIsNotNone(result)
        self.assertFalse(result.is_authenticated_utfpr)
        self.assertFalse(result.email_verified)
        self.assertEqual(result.email, new_email)

    def test_link_user_returns_none_when_authentication_fails(self):
        result = self.service.link_user(self.phone, "000000", "senha", self.email)
        self.assertIsNone(result)


class LogoutTests(TestCase):
    def setUp(self):
        self.service = UTFPRAuthService()
        self.phone = "5588888888888@c.us"
        self.user = UserProfile.objects.create(
            phone_number=self.phone,
            ra="a1234567",
            email="aluno@alunos.utfpr.edu.br",
            email_verified=True,
            is_authenticated_utfpr=True,
        )

    def test_logout_preserves_verified_email_and_ra(self):
        self.assertTrue(self.service.logout(self.phone))

        self.user.refresh_from_db()
        self.assertFalse(self.user.is_authenticated_utfpr)
        # Dados preservados para permitir re-login sem nova verificação
        self.assertEqual(self.user.email, "aluno@alunos.utfpr.edu.br")
        self.assertTrue(self.user.email_verified)
        self.assertEqual(self.user.ra, "a1234567")

    def test_logout_returns_false_for_unknown_user(self):
        self.assertFalse(self.service.logout("inexistente@c.us"))
