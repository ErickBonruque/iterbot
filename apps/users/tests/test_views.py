"""Tests for success_page and ConfirmEmailView.

Verifies FIX-04: email confirmation auto-login and success page access.
"""

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.jobs.models import Company
from apps.users.models import UserProfile
from apps.users.services import UTFPRAuthService

CACHES_LOCMEM = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
    }
}


class TestSuccessPage(TestCase):
    """Tests for the success page accessibility and content."""

    def test_success_page_anonymous_accessible(self):
        """success_page should be accessible without login (no @login_required)."""
        response = self.client.get(reverse("account_success"))
        # Was 302 redirect to login when @login_required; now should be 200
        self.assertEqual(response.status_code, 200)

    def test_success_page_authenticated_shows_email(self):
        """Logged-in user sees their email on success page."""
        user = User.objects.create_user(
            username="student@test.com",
            email="student@test.com",
            password="TestPass123!",
        )
        self.client.force_login(user)
        response = self.client.get(reverse("account_success"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, user.email)

    def test_success_page_anonymous_shows_login_link(self):
        """Anonymous user sees login link on success page."""
        response = self.client.get(reverse("account_success"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse("account_login"))

    def test_success_page_company_user_shows_profile_link(self):
        """Company user sees link to company profile."""
        user = User.objects.create_user(
            username="company@test.com",
            email="company@test.com",
            password="TestPass123!",
        )
        Company.objects.create(
            user=user,
            cnpj="11.222.333/0001-81",
            nome="Empresa Teste",
            email="company@test.com",
            telefone="(41) 99999-0000",
            contato_nome="Joao",
            contato_cargo="Gerente",
        )
        self.client.force_login(user)
        response = self.client.get(reverse("account_success"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "/empresas/perfil/")


class TestConfirmEmailView(TestCase):
    """Tests for ConfirmEmailView auto-login and redirect behavior."""

    def setUp(self):
        self.service = UTFPRAuthService()

    def _create_profile_with_token(self, email, token, phone_suffix="9999"):
        """Helper: Create a UserProfile with a confirmation token set."""
        profile = UserProfile.objects.create(
            phone_number=f"55419{phone_suffix}@c.us",
            email=email,
            ra=f"a{phone_suffix}",
            email_confirmation_token=token,
            email_confirmation_sent_at=timezone.now(),
            email_verified=False,
            is_authenticated_utfpr=False,
        )
        return profile

    def test_confirm_email_auto_login_student_redirects_to_success(self):
        """Student confirms email → auto-logged in → redirect to /accounts/success/."""
        profile = self._create_profile_with_token(
            email="student@alunos.utfpr.edu.br",
            token="student-token-abc",
        )

        response = self.client.get(reverse("confirm_email", kwargs={"token": "student-token-abc"}))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "/accounts/success/")

        # Verify profile was verified
        profile.refresh_from_db()
        self.assertTrue(profile.email_verified)

        # Verify user is authenticated in session
        user = User.objects.get(email="student@alunos.utfpr.edu.br")
        self.assertEqual(str(self.client.session.get("_auth_user_id")), str(user.pk))

    def test_confirm_email_auto_login_company_redirects_to_profile(self):
        """Company user confirms email → auto-logged in → redirect to /empresas/perfil/."""
        # Create User + Company
        user = User.objects.create_user(
            username="empresa@test.com",
            email="empresa@test.com",
            password="TestPass123!",
        )
        Company.objects.create(
            user=user,
            cnpj="22.333.444/0001-90",
            nome="Empresa Alpha",
            email="empresa@test.com",
            telefone="(41) 88888-0000",
            contato_nome="Maria",
            contato_cargo="Diretora",
        )

        # Create UserProfile linked to this user for email confirmation
        profile, _ = UserProfile.objects.get_or_create(
            user=user,
            defaults={
                "phone_number": "5541777777777@c.us",
                "email": "empresa@test.com",
                "email_confirmation_token": "company-token-xyz",
                "email_confirmation_sent_at": timezone.now(),
                "email_verified": False,
                "is_authenticated_utfpr": False,
            },
        )
        # Ensure token is set (profile may already exist via signal)
        profile.email_confirmation_token = "company-token-xyz"
        profile.email_confirmation_sent_at = timezone.now()
        profile.email_verified = False
        profile.save()

        response = self.client.get(reverse("confirm_email", kwargs={"token": "company-token-xyz"}))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "/empresas/perfil/")

    def test_confirm_email_invalid_token_shows_error(self):
        """Confirming with invalid token → no login, shows error page."""
        response = self.client.get(reverse("confirm_email", kwargs={"token": "nonexistent-token"}))

        # Should render email_confirmed with failure message (200)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "expirado")
        # User should NOT be authenticated
        self.assertFalse("_auth_user_id" in self.client.session)

    def test_confirm_email_creates_user_if_missing(self):
        """Bot user (no Django User) confirms email → User created and logged in."""
        profile = self._create_profile_with_token(
            email="newbot@alunos.utfpr.edu.br",
            token="bot-new-user-token",
            phone_suffix="0001",
        )
        # Verify no User exists yet
        self.assertFalse(User.objects.filter(email=profile.email).exists())
        self.assertIsNone(profile.user)

        response = self.client.get(reverse("confirm_email", kwargs={"token": "bot-new-user-token"}))

        self.assertEqual(response.status_code, 302)
        # Verify User was created and linked
        profile.refresh_from_db()
        self.assertIsNotNone(profile.user)
        self.assertEqual(profile.user.email, profile.email)
        self.assertTrue(profile.email_verified)
