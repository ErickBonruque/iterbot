import requests
import structlog

from config.env import WahaSettings

logger = structlog.get_logger(__name__)


class WahaClient:
    """Cliente para interagir com a API do WAHA.

    Attributes:
        settings: WAHA configuration settings.
    """

    def __init__(self, settings: WahaSettings | None = None) -> None:
        """Initialize the WAHA client.

        Args:
            settings: WAHA configuration settings. Defaults to WahaSettings().
        """
        self.settings = settings or WahaSettings()

    def _normalize_chat_id(self, chat_id: str) -> str:
        """Normalize WhatsApp chat ID to WAHA format.

        Args:
            chat_id: Raw chat ID from WhatsApp message.

        Returns:
            Normalized chat ID with @c.us suffix if not present.
        """
        if "@" in chat_id:
            return chat_id
        return f"{chat_id}@c.us"

    def send_message(self, chat_id: str, text: str) -> bool:
        """Send a text message via WAHA.

        Args:
            chat_id: WhatsApp chat identifier.
            text: Message text to send.

        Returns:
            True if message was sent successfully, False otherwise.
        """
        url = f"{self.settings.base_url}/api/sendText"
        headers = {
            "X-Api-Key": self.settings.api_key,
            "Content-Type": "application/json",
        }
        payload = {
            "chatId": self._normalize_chat_id(chat_id),
            "text": text,
            "session": self.settings.session_name,
        }
        try:
            response = requests.post(
                url, json=payload, headers=headers, timeout=self.settings.timeout_seconds
            )
            if not 200 <= response.status_code < 300:
                logger.error(
                    "waha_send_message_error",
                    session_name=self.settings.session_name,
                    status_code=response.status_code,
                )
                return False
        except Exception as error:  # pragma: no cover - defensive logging
            logger.error(
                "waha_send_message_exception",
                session_name=self.settings.session_name,
                error=str(error),
            )
            return False

        return True

    def start_session(self) -> bool:
        """Start (or restart) the WAHA session via API.

        Args:
            None

        Returns:
            True if session entered WORKING or STARTING state, False on HTTP
            error, timeout, or connection failure.
        """
        url = f"{self.settings.base_url}/api/sessions/{self.settings.session_name}/start"
        headers = {
            "X-Api-Key": self.settings.api_key,
            "Content-Type": "application/json",
        }
        try:
            response = requests.post(
                url,
                headers=headers,
                timeout=self.settings.timeout_seconds,
            )
            if 200 <= response.status_code < 300:
                logger.info(
                    "waha_session_start_success",
                    session_name=self.settings.session_name,
                    status_code=response.status_code,
                )
                return True
            else:
                logger.error(
                    "waha_session_start_failed",
                    session_name=self.settings.session_name,
                    status_code=response.status_code,
                )
                return False
        except requests.exceptions.Timeout:
            logger.error(
                "waha_session_start_timeout",
                session_name=self.settings.session_name,
                timeout_seconds=self.settings.timeout_seconds,
            )
            return False
        except requests.exceptions.ConnectionError as error:
            logger.error(
                "waha_session_start_connection_error",
                session_name=self.settings.session_name,
                error=str(error),
            )
            return False
        except Exception as error:  # pragma: no cover - defensive
            logger.error(
                "waha_session_start_unexpected_error",
                session_name=self.settings.session_name,
                error=str(error),
            )
            return False
