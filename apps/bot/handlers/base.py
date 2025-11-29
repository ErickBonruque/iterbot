"""Base handler for bot conversation flows."""
from abc import ABC, abstractmethod
from typing import Optional

import structlog

from apps.bot.models import BotMessage, InteractionLog
from apps.users.models import UserProfile
from infra.waha.client import WahaClient

logger = structlog.get_logger(__name__)


class BaseHandler(ABC):
    """Abstract base class for conversation handlers following SRP."""

    BRAND_HEADER = (
        "🌟 *CapyVagas* | Assistente de Vagas da UTFPR\n"
        "Conecto você às oportunidades certas para o seu curso."
    )

    def __init__(self, waha_client: WahaClient) -> None:
        """
        Initialize handler with WAHA client.
        
        Args:
            waha_client: Client for sending WhatsApp messages
        """
        self.waha_client = waha_client

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

    def send_msg(self, user: UserProfile, chat_id: str, message: str) -> None:
        """
        Send message to user and log it.
        
        Args:
            user: User profile to send message to
            chat_id: WhatsApp chat ID
            message: Message text to send
        """
        try:
            self.waha_client.send_message(chat_id, message)
            self._log_sent(user, message)
        except Exception as e:
            logger.error(
                "failed_to_send_message",
                user_id=user.id,
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
                session_id=self.waha_client.settings.session_name,
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
