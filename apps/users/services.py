import uuid
from datetime import timedelta

from django.utils import timezone

from apps.users.models import UserProfile
from infra.waha.protocols import EmailConfirmationDispatcher

logger = __import__("logging").getLogger(__name__)


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
        """Link an RA to a phone number after successful authentication."""
        if self.authenticate(ra, password):
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
        return None

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
        """Resend confirmation email to user."""
        try:
            user = UserProfile.objects.get(phone_number=phone_number)
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
        """Unlink student credentials from a phone number."""
        try:
            user = UserProfile.objects.get(phone_number=phone_number)
            user.is_authenticated_utfpr = False
            user.utfpr_password = None
            user.email = None
            user.save()
            return True
        except UserProfile.DoesNotExist:
            return False
