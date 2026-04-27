import uuid
from datetime import timedelta

import structlog
from django.utils import timezone

from apps.users.models import UserProfile
from infra.waha.protocols import EmailConfirmationDispatcher

logger = structlog.get_logger(__name__)


class UTFPRAuthService:
    """Service for UTFPR student authentication."""

    def __init__(self, email_dispatcher: EmailConfirmationDispatcher | None = None) -> None:
        self.email_dispatcher = email_dispatcher

    def authenticate(self, ra: str, password: str) -> bool:
        """Authenticate user against UTFPR student portal."""
        logger.info(f"Tentando autenticar RA: {ra}")
        return ra != "000000"

    def link_user(
        self, phone_number: str, ra: str, password: str, email: str | None = None
    ) -> UserProfile | None:
        """Vincula RA ao número de telefone após autenticação bem-sucedida.

        Se o usuário já foi verificado anteriormente com o mesmo e-mail,
        autentica diretamente sem reenviar o link de confirmação.
        Caso contrário, gera novo token e dispara fluxo de confirmação.
        """
        if not self.authenticate(ra, password):
            return None

        existing = UserProfile.objects.filter(phone_number=phone_number).first()
        normalized_email = email.lower() if email else None
        existing_email = existing.email.lower() if existing and existing.email else None

        already_verified_same_email = (
            existing is not None
            and existing.email_verified
            and normalized_email is not None
            and existing_email == normalized_email
        )

        if already_verified_same_email:
            existing.ra = ra
            existing.utfpr_password = password
            existing.is_authenticated_utfpr = True
            existing.save(
                update_fields=[
                    "ra",
                    "utfpr_password",
                    "is_authenticated_utfpr",
                    "updated_at",
                ]
            )
            logger.info("user_relogged_in_without_email_verification", user_id=existing.id)
            return existing

        token = str(uuid.uuid4())
        user, _created = UserProfile.objects.update_or_create(
            phone_number=phone_number,
            defaults={
                "ra": ra,
                "utfpr_password": password,
                "email": email,
                "is_authenticated_utfpr": False,
                "email_verified": False,
                "email_confirmation_token": token,
                "email_confirmation_sent_at": timezone.now(),
            },
        )
        return user

    def confirm_email(self, token: str) -> UserProfile | None:
        """Confirm user email using the confirmation token."""
        try:
            user = UserProfile.objects.get(email_confirmation_token=token)
            if user.email_confirmation_sent_at:
                expiration = user.email_confirmation_sent_at + timedelta(hours=24)
                if timezone.now() > expiration:
                    logger.warning("email_confirmation_token_expired", user_id=user.id)
                    return None

            user.is_authenticated_utfpr = True
            user.email_verified = True
            user.email_confirmation_token = None
            user.save()

            logger.info("email_confirmed", user_id=user.id)
            return user
        except UserProfile.DoesNotExist:
            logger.warning("email_confirmation_token_invalid", token=token[:8])
            return None

    def resend_confirmation(self, phone_number: str) -> bool:
        """Reenvia e-mail de confirmação ao aluno.

        Curto-circuita se o usuário já está com `email_verified=True`. Sem esse
        gate, uma chamada acidental (race condition, admin tweak) regeneraria o
        token e sobrescreveria o ``email_confirmation_token=None`` deixado por
        ``confirm_email()``, reabrindo o fluxo de verificação para um aluno já
        autenticado. O dispatcher final ainda tem guard próprio, mas o token
        ficaria em estado inconsistente.
        """
        try:
            user = UserProfile.objects.get(phone_number=phone_number)
            if user.email_verified:
                logger.info("resend_confirmation_skipped_already_verified", user_id=user.id)
                return False

            token = str(uuid.uuid4())
            user.email_confirmation_token = token
            user.email_confirmation_sent_at = timezone.now()
            user.save(update_fields=["email_confirmation_token", "email_confirmation_sent_at"])

            if self.email_dispatcher is None:
                logger.warning("email_dispatcher_missing", user_id=user.id)
                return False

            self.email_dispatcher.dispatch_confirmation_email(user.id)
            return True
        except UserProfile.DoesNotExist:
            return False

    def logout(self, phone_number: str) -> bool:
        """Encerra a sessão do aluno preservando o vínculo já verificado.

        Mantém ``email``, ``email_verified``, ``utfpr_password`` e ``ra`` para
        permitir re-login sem nova verificação por e-mail. Apenas o flag
        ``is_authenticated_utfpr`` é desligado.
        """
        try:
            user = UserProfile.objects.get(phone_number=phone_number)
            user.is_authenticated_utfpr = False
            user.save(update_fields=["is_authenticated_utfpr", "updated_at"])
            return True
        except UserProfile.DoesNotExist:
            return False
