"""Login de empresa pelo WhatsApp (CompanyAuthService.authenticate_company).

Usa a mesma senha do portal, mas não passa pelo allauth — então precisa do seu
próprio bloqueio: 5 senhas erradas para o mesmo e-mail travam por
ACCOUNT_LOGIN_ATTEMPTS_TIMEOUT (mesmos números do portal).
"""

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase

from apps.companies.company_auth_service import CompanyAuthService
from apps.jobs.models import Company, CompanyStatus

PHONE = "5545999991111@c.us"
EMAIL = "rh@empresa.com"
PASSWORD = "SenhaCerta!23"


class CompanyWhatsappLoginTests(TestCase):
    def setUp(self):
        cache.clear()
        user = User.objects.create_user(username="rh", email=EMAIL, password=PASSWORD)
        Company.objects.create(
            user=user,
            cnpj="11.222.333/0001-81",
            nome="Empresa",
            email=EMAIL,
            telefone="(45) 99999-0000",
            contato_nome="Ana",
            contato_cargo="RH",
            status=CompanyStatus.APPROVED,
        )
        self.service = CompanyAuthService()

    def test_correct_password_authenticates(self):
        profile = self.service.authenticate_company(PHONE, EMAIL, PASSWORD)
        self.assertIsNotNone(profile)
        self.assertTrue(profile.is_company_authenticated)

    def test_five_wrong_passwords_lock_the_email(self):
        for _ in range(5):
            self.assertIsNone(self.service.authenticate_company(PHONE, EMAIL, "errada"))

        self.assertIsNone(self.service.authenticate_company(PHONE, EMAIL, PASSWORD))

    def test_lock_counts_across_whatsapp_numbers(self):
        """Trocar de número não zera o bloqueio — ele é por e-mail da empresa."""
        for i in range(5):
            self.service.authenticate_company(f"55459000000{i}@c.us", EMAIL, "errada")

        self.assertIsNone(self.service.authenticate_company(PHONE, EMAIL, PASSWORD))

    def test_success_resets_the_counter(self):
        for _ in range(4):
            self.service.authenticate_company(PHONE, EMAIL, "errada")
        self.assertIsNotNone(self.service.authenticate_company(PHONE, EMAIL, PASSWORD))

        for _ in range(4):
            self.service.authenticate_company(PHONE, EMAIL, "errada")
        self.assertIsNotNone(self.service.authenticate_company(PHONE, EMAIL, PASSWORD))
