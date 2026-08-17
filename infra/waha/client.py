import base64
from dataclasses import dataclass

import requests
import structlog

from config.env import WahaSettings

logger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class QrCodeResult:
    """Resultado de uma tentativa de obter o QR code de pareamento.

    Attributes:
        image: Data URI pronto para um `<img src>`, ou None se indisponível.
        session_status: Estado da sessão informado pelo WAHA (ex.: FAILED).
        error: Mensagem para exibir ao operador quando não há QR.
    """

    image: str | None = None
    session_status: str | None = None
    error: str | None = None

    @property
    def available(self) -> bool:
        return self.image is not None


class WahaClient:
    """Cliente para interagir com a API do WAHA.

    Attributes:
        settings: WAHA configuration settings.
    """

    # O endpoint de QR segura a requisição enquanto o WAHA tenta produzir o
    # código: medido em produção, ele leva ~10s só para responder 422 quando a
    # sessão não está em SCAN_QR_CODE. O timeout padrão do cliente (5s) cortava
    # a chamada antes de qualquer resposta.
    QR_TIMEOUT_SECONDS = 25

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

    def _post_session_action(self, action: str) -> bool:
        """POST em /api/sessions/{sessao}/{action}, traduzindo falhas em False.

        Args:
            action: Ação do ciclo de vida da sessão (start, stop, logout).

        Returns:
            True se o WAHA respondeu 2xx, False em erro HTTP, timeout ou falha
            de conexão — nenhuma exceção escapa para o chamador.
        """
        url = f"{self.settings.base_url}/api/sessions/{self.settings.session_name}/{action}"
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
                    "waha_session_action_success",
                    action=action,
                    session_name=self.settings.session_name,
                    status_code=response.status_code,
                )
                return True
            else:
                logger.error(
                    "waha_session_action_failed",
                    action=action,
                    session_name=self.settings.session_name,
                    status_code=response.status_code,
                )
                return False
        except requests.exceptions.Timeout:
            logger.error(
                "waha_session_action_timeout",
                action=action,
                session_name=self.settings.session_name,
                timeout_seconds=self.settings.timeout_seconds,
            )
            return False
        except requests.exceptions.ConnectionError as error:
            logger.error(
                "waha_session_action_connection_error",
                action=action,
                session_name=self.settings.session_name,
                error=str(error),
            )
            return False
        except Exception as error:  # pragma: no cover - defensive
            logger.error(
                "waha_session_action_unexpected_error",
                action=action,
                session_name=self.settings.session_name,
                error=str(error),
            )
            return False

    def start_session(self) -> bool:
        """Start (or restart) the WAHA session via API.

        Args:
            None

        Returns:
            True if session entered WORKING or STARTING state, False on HTTP
            error, timeout, or connection failure.
        """
        return self._post_session_action("start")

    def logout_session(self) -> bool:
        """Desconecta o número pareado e devolve a sessão para SCAN_QR_CODE.

        Necessário quando as credenciais salvas não valem mais (sessão presa em
        FAILED) ou para trocar o número do bot: sem o logout, o WAHA tenta
        reusar a sessão antiga e nunca gera um QR novo.

        Returns:
            True se o WAHA aceitou o logout, False em qualquer falha.
        """
        return self._post_session_action("logout")

    def get_qr(self) -> QrCodeResult:
        """Busca o QR code de pareamento da sessão.

        O WAHA só entrega o QR quando a sessão está em SCAN_QR_CODE; nos demais
        estados responde 422 com o status atual, que devolvemos para a tela do
        admin orientar o próximo passo em vez de mostrar um erro cru.

        Returns:
            QrCodeResult com o data URI da imagem ou com o motivo da ausência.
        """
        url = f"{self.settings.base_url}/api/{self.settings.session_name}/auth/qr"
        headers = {
            "X-Api-Key": self.settings.api_key,
            "Accept": "image/png",
        }
        try:
            response = requests.get(
                url,
                headers=headers,
                params={"format": "image"},
                timeout=self.QR_TIMEOUT_SECONDS,
            )
        except requests.exceptions.RequestException as error:
            logger.error(
                "waha_qr_request_failed",
                session_name=self.settings.session_name,
                error=str(error),
            )
            return QrCodeResult(error="Não foi possível falar com o WAHA.")

        content_type = response.headers.get("Content-Type", "").split(";")[0].strip()
        if 200 <= response.status_code < 300 and content_type.startswith("image/"):
            encoded = base64.b64encode(response.content).decode("ascii")
            return QrCodeResult(image=f"data:{content_type};base64,{encoded}")

        try:
            payload = response.json()
        except ValueError:
            payload = {}

        session_status = payload.get("status")
        logger.warning(
            "waha_qr_unavailable",
            session_name=self.settings.session_name,
            status_code=response.status_code,
            session_status=session_status,
        )
        return QrCodeResult(
            session_status=session_status,
            error=payload.get("error") or f"WAHA respondeu {response.status_code}.",
        )
