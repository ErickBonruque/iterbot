import uuid
from datetime import timedelta

import structlog
from django.conf import settings
from django.utils import timezone

from apps.users.models import UserProfile
from infra.waha.protocols import EmailConfirmationDispatcher

logger = structlog.get_logger(__name__)


class EmailEmUsoError(Exception):
    """O e-mail @alunos já está vinculado a outro número de WhatsApp."""


def is_student_test_email(email: str | None) -> bool:
    """E-mail de aluno fictício (``STUDENT_TEST_EMAILS``) aceito sem o link.

    Serve para testadores sem e-mail @alunos usarem os fluxos do aluno. Nenhum
    e-mail é enviado a esses endereços; esvaziar a variável desliga o atalho.
    """
    return bool(email) and email.strip().lower() in settings.STUDENT_TEST_EMAILS


class UTFPRAuthService:
    """Cadastro de aluno: RA + e-mail @alunos confirmado por link."""

    def __init__(self, email_dispatcher: EmailConfirmationDispatcher | None = None) -> None:
        self.email_dispatcher = email_dispatcher

    def link_user(self, phone_number: str, ra: str, email: str | None = None) -> UserProfile | None:
        """Vincula RA e e-mail @alunos ao número de telefone.

        Não há senha: a prova de que a pessoa é aluna é o link de confirmação
        enviado ao e-mail institucional. Se o usuário já foi verificado com o
        mesmo e-mail, autentica direto sem reenviar o link; caso contrário,
        gera novo token (o envio do e-mail fica a cargo de quem chama).
        """
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
            existing.is_authenticated_utfpr = True
            existing.save(update_fields=["ra", "is_authenticated_utfpr", "updated_at"])
            logger.info("user_relogged_in_without_email_verification", user_id=existing.id)
            return existing

        # E-mail é único: sem esta checagem o update_or_create estoura
        # IntegrityError quando outro número já usa o mesmo endereço.
        if (
            normalized_email
            and UserProfile.objects.filter(email__iexact=normalized_email)
            .exclude(phone_number=phone_number)
            .exists()
        ):
            raise EmailEmUsoError(normalized_email)

        if is_student_test_email(normalized_email):
            user, _created = UserProfile.objects.update_or_create(
                phone_number=phone_number,
                defaults={
                    "ra": ra,
                    "email": normalized_email,
                    "is_authenticated_utfpr": True,
                    "email_verified": True,
                    "email_confirmation_token": None,
                    "email_confirmation_sent_at": None,
                },
            )
            logger.info("student_test_email_linked", user_id=user.id)
            return user

        token = str(uuid.uuid4())
        user, _created = UserProfile.objects.update_or_create(
            phone_number=phone_number,
            defaults={
                "ra": ra,
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

        Mantém ``email``, ``email_verified`` e ``ra`` para
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
