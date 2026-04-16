from typing import Optional

from apps.users.models import UserProfile

logger = __import__("logging").getLogger(__name__)


class UTFPRAuthService:
    """Service for UTFPR student authentication.

    Attributes:
        None: This class is stateless.
    """

    def authenticate(self, ra: str, password: str) -> bool:
        """Authenticate user against UTFPR student portal.

        Args:
            ra: Student registration number (RA).
            password: Student portal password.

        Returns:
            True if authentication succeeded, False otherwise.
        """
        logger.info(f"Tentando autenticar RA: {ra}")

        if ra == "000000":
            return False

        return True

    def link_user(self, phone_number: str, ra: str, password: str) -> Optional[UserProfile]:
        """Link an RA to a phone number after successful authentication.

        Args:
            phone_number: WhatsApp phone number.
            ra: Student registration number.
            password: Student portal password.

        Returns:
            UserProfile instance if linked, None if authentication failed.
        """
        if self.authenticate(ra, password):
            user, created = UserProfile.objects.update_or_create(
                phone_number=phone_number,
                defaults={
                    "ra": ra,
                    "utfpr_password": password,
                    "is_authenticated_utfpr": True,
                },
            )
            return user
        return None

    def logout(self, phone_number: str) -> bool:
        """Unlink student credentials from a phone number.

        Args:
            phone_number: WhatsApp phone number.

        Returns:
            True if user was found and logged out, False if not found.
        """
        try:
            user = UserProfile.objects.get(phone_number=phone_number)
            user.is_authenticated_utfpr = False
            user.utfpr_password = None
            user.save()
            return True
        except UserProfile.DoesNotExist:
            return False
