"""Base handler for bot conversation flows."""

from abc import ABC, abstractmethod
from typing import Any

import structlog

from apps.bot.models import BotMessage, InteractionLog
from apps.users.models import UserProfile
from infra.waha.protocols import MessageSender

logger = structlog.get_logger(__name__)


class _SafeFormatDict(dict[str, Any]):
    """Returns original placeholder when key is missing."""

    def __missing__(self, key: str) -> str:  # pragma: no cover - trivial
        return "{" + key + "}"


class BaseHandler(ABC):
    """Abstract base class for conversation handlers following SRP.

    Attributes:
        waha_client: Message sender contract used by handlers.
        BRAND_HEADER: Brand header text used in messages.
    """

    BRAND_HEADER = (
        "🌟 *IterBot* | Assistente de Vagas da UTFPR\n"
        "Conecto você às oportunidades certas para o seu curso."
    )

    def __init__(self, waha_client: MessageSender) -> None:
        """
        Initialize handler with message sender contract.

        Args:
            waha_client: Sender used for outbound bot messages.
        """
        self.waha_client = waha_client

    def _session_name(self) -> str:
        settings = getattr(self.waha_client, "settings", None)
        return getattr(settings, "session_name", "unknown")

    def get_text(self, key: str, default: str) -> str:
        """
        Fetch configured message or use default.

        Args:
            key: Message key to lookup
            default: Default message if key not found

        Returns:
            Configured or default message text
        """
        try:
            msg = BotMessage.objects.filter(key=key).first()
            if msg and msg.text.strip():
                return msg.text
        except Exception as e:
            logger.warning("failed_to_fetch_message", key=key, error=str(e))
        return default

    def resolve_message(self, key: str, default: str, **kwargs: Any) -> str:
        """Resolve message from DB override and format named placeholders safely."""
        template = self.get_text(key, default)
        if not kwargs:
            return template

        try:
            return template.format_map(_SafeFormatDict(kwargs))
        except Exception as e:
            logger.warning(
                "failed_to_render_message_template",
                key=key,
                error=str(e),
                placeholders=sorted(kwargs.keys()),
            )
            return template

    def send_msg(self, user: UserProfile, chat_id: str, message: str) -> None:
        """
        Send message to user and log it.

        Args:
            user: User profile to send message to
            chat_id: WhatsApp chat ID
            message: Message text to send
        """
        try:
            success = self.waha_client.send_message(chat_id, message)
            if not success:
                # WahaClient retorna False para HTTP não-2xx (não levanta exceção)
                from apps.bot.models.bot_action_log import (
                    BotActionLog,  # import local: evita circular import
                )

                BotActionLog.objects.create(
                    user=user,
                    action_type="WAHA_SEND",
                    status="ERROR",
                    error_type="WAHA_SEND_FAIL",
                    metadata={"chat_id": chat_id, "msg_preview": message[:100]},
                )
                logger.error(
                    "waha_send_fail",
                    user_id=user.id if user else None,
                    chat_id=chat_id,
                )
            else:
                self._log_sent(user, message)
        except Exception as e:
            from apps.bot.models.bot_action_log import (
                BotActionLog,  # import local: evita circular import
            )

            BotActionLog.objects.create(
                user=user,
                action_type="WAHA_SEND",
                status="ERROR",
                error_type="EXCEPTION",
                error_message=str(e),
                metadata={"chat_id": chat_id},
            )
            logger.error(
                "failed_to_send_message",
                user_id=user.id if user else None,
                chat_id=chat_id,
                error=str(e),
                exc_info=True,
            )

    def _log_sent(self, user: UserProfile, message: str) -> None:
        """
        Log sent message to database.

        Args:
            user: User profile
            message: Message text that was sent
        """
        try:
            InteractionLog.objects.create(
                user=user,
                message_content=message,
                message_type="SENT",
                session_id=self._session_name(),
            )
        except Exception as e:
            logger.error(
                "failed_to_log_message",
                user_id=user.id,
                error=str(e),
            )

    @abstractmethod
    def handle(self, user: UserProfile, chat_id: str, text: str) -> bool:
        """
        Handle user message in this conversation flow.

        Args:
            user: User profile
            chat_id: WhatsApp chat ID
            text: User message text

        Returns:
            True if message was handled, False otherwise
        """
        pass
