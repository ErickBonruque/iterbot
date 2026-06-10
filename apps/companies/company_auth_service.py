"""Serviço de autenticação de empresa via WhatsApp."""

import uuid
from datetime import timedelta

import structlog
from django.utils import timezone

from apps.jobs.models.company import Company
from apps.users.models import UserProfile

logger = structlog.get_logger(__name__)


class CompanyAuthService:
    """Gerencia vínculo entre número WhatsApp e conta de empresa no portal."""

    def link_company_by_email(self, phone_number: str, company_email: str) -> UserProfile | None:
        """Localiza empresa pelo email, gera token e prepara perfil para confirmação.

        Retorna o UserProfile atualizado (token gerado, company linkada) para que
        o caller possa disparar o email. Retorna None se empresa não encontrada.
        """
        try:
            company = Company.objects.get(email=company_email.strip().lower())
        except Company.DoesNotExist:
            logger.info("company_link_not_found", email=company_email)
            return None

        token = str(uuid.uuid4())
        profile, _ = UserProfile.objects.get_or_create(phone_number=phone_number)
        profile.company = company
        profile.is_company_authenticated = False
        profile.company_confirmation_token = token
        profile.company_confirmation_sent_at = timezone.now()
        profile.save(
            update_fields=[
                "company",
                "is_company_authenticated",
                "company_confirmation_token",
                "company_confirmation_sent_at",
                "updated_at",
            ]
        )
        logger.info("company_link_token_generated", user_id=profile.id, company_id=company.id)
        return profile

    def confirm_company_email(self, token: str) -> UserProfile | None:
        """Confirma o vínculo WhatsApp-empresa via token recebido no email.

        Seta is_company_authenticated=True e limpa o token.
        Retorna None se token inválido ou expirado (24h).
        """
        try:
            profile = UserProfile.objects.select_related("company").get(
                company_confirmation_token=token
            )
        except UserProfile.DoesNotExist:
            logger.warning("company_confirmation_token_invalid", token=token[:8])
            return None

        if profile.company_confirmation_sent_at:
            expiry = profile.company_confirmation_sent_at + timedelta(hours=24)
            if timezone.now() > expiry:
                logger.warning("company_confirmation_token_expired", user_id=profile.id)
                return None

        profile.is_company_authenticated = True
        profile.company_confirmation_token = None
        profile.save(
            update_fields=["is_company_authenticated", "company_confirmation_token", "updated_at"]
        )
        logger.info("company_confirmed", user_id=profile.id, company_id=profile.company_id)
        return profile

    def authenticate_company(
        self, phone_number: str, company_email: str, password: str
    ) -> UserProfile | None:
        """Autentica empresa pelo e-mail e senha do portal.

        Retorna UserProfile com is_company_authenticated=True se credenciais válidas,
        None caso contrário.
        """
        from django.contrib.auth.models import User

        try:
            company = Company.objects.get(email=company_email.strip().lower())
        except Company.DoesNotExist:
            logger.info("company_auth_not_found", email=company_email)
            return None

        # Localiza o auth.User pelo email da empresa.
        try:
            auth_user = User.objects.get(email=company_email.strip().lower())
        except User.DoesNotExist:
            logger.info("company_auth_user_not_found", email=company_email)
            return None

        if not auth_user.check_password(password):
            logger.info("company_auth_wrong_password", email=company_email)
            return None

        profile, _ = UserProfile.objects.get_or_create(phone_number=phone_number)
        profile.company = company
        profile.is_company_authenticated = True
        profile.company_confirmation_token = None
        profile.save(
            update_fields=[
                "company",
                "is_company_authenticated",
                "company_confirmation_token",
                "updated_at",
            ]
        )
        logger.info("company_authenticated", user_id=profile.id, company_id=company.id)
        return profile

    def logout_company(self, phone_number: str) -> bool:
        """Encerra sessão empresa preservando o vínculo para re-login rápido."""
        try:
            profile = UserProfile.objects.get(phone_number=phone_number)
            profile.is_company_authenticated = False
            profile.save(update_fields=["is_company_authenticated", "updated_at"])
            logger.info("company_logged_out", user_id=profile.id)
            return True
        except UserProfile.DoesNotExist:
            return False

    def reauth_company(self, phone_number: str) -> bool:
        """Re-autentica empresa que já tem vínculo confirmado, sem reenviar email."""
        try:
            profile = UserProfile.objects.get(phone_number=phone_number)
            if profile.company is None:
                return False
            profile.is_company_authenticated = True
            profile.save(update_fields=["is_company_authenticated", "updated_at"])
            logger.info("company_reauthed", user_id=profile.id, company_id=profile.company_id)
            return True
        except UserProfile.DoesNotExist:
            return False
