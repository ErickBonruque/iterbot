"""Protocol contracts for bot dependency injection."""

from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from apps.users.models import UserProfile


class MessageSender(Protocol):
    """Contract for sending outbound messages."""

    def send_message(self, chat_id: str, text: str) -> bool:
        """Send a message to a chat destination."""


class JobSearcher(Protocol):
    """Contract for searching jobs from configured sources."""

    def search(self, terms: list[str], limit: int = 5) -> list[dict[str, Any]]:
        """Return job results filtered by terms."""


class Authenticator(Protocol):
    """Contract for UTFPR authentication and account lifecycle."""

    def authenticate(self, ra: str, password: str) -> bool:
        """Validate UTFPR credentials."""

    def link_user(
        self,
        phone_number: str,
        ra: str,
        password: str,
        email: str | None = None,
    ) -> "UserProfile | None":
        """Link a phone number to UTFPR credentials."""

    def resend_confirmation(self, phone_number: str) -> bool:
        """Resend confirmation flow for a user."""

    def logout(self, phone_number: str) -> bool:
        """Logout user and clear persisted auth data."""


class EmailConfirmationDispatcher(Protocol):
    """Contract for dispatching async email confirmations."""

    def dispatch_confirmation_email(self, user_id: int) -> None:
        """Dispatch confirmation email job for a user id."""
