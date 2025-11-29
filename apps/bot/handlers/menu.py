"""Menu handler for displaying navigation options."""
import structlog

from apps.users.models import UserProfile

from .base import BaseHandler

logger = structlog.get_logger(__name__)


class MenuHandler(BaseHandler):
    """Handles menu display and navigation."""

    def send_menu(self, user: UserProfile, chat_id: str) -> None:
        """
        Send main menu to user.
        
        Args:
            user: User profile
            chat_id: WhatsApp chat ID
        """
        if user.is_authenticated_utfpr:
            menu_text = (
                f"{self.BRAND_HEADER}\n\n"
                f"👤 *Usuário*: {user.ra or 'Não cadastrado'}\n\n"
                "📋 *Menu Principal*:\n"
                "1️⃣ Atualizar Cadastro\n"
                "2️⃣ Sair da Conta\n"
                "3️⃣ Buscar Vagas\n\n"
                "Digite o número da opção desejada."
            )
        else:
            menu_text = (
                f"{self.BRAND_HEADER}\n\n"
                "📋 *Menu Principal*:\n"
                "1️⃣ Fazer Cadastro/Login\n"
                "3️⃣ Buscar Vagas\n\n"
                "Digite o número da opção desejada."
            )

        self.send_msg(user, chat_id, menu_text)
        logger.info("menu_displayed", user_id=user.id, authenticated=user.is_authenticated_utfpr)

    def send_unknown_command(self, user: UserProfile, chat_id: str) -> None:
        """
        Send unknown command message.
        
        Args:
            user: User profile
            chat_id: WhatsApp chat ID
        """
        msg = self.get_text(
            "unknown_command",
            "❓ Comando não reconhecido.\n\n"
            "Digite *menu* para ver as opções disponíveis.",
        )
        self.send_msg(user, chat_id, msg)
        logger.debug("unknown_command_sent", user_id=user.id)

    def handle(self, user: UserProfile, chat_id: str, text: str) -> bool:
        """
        Handle menu-related commands.
        
        Args:
            user: User profile
            chat_id: WhatsApp chat ID
            text: User message
            
        Returns:
            True if message was handled
        """
        # This handler doesn't process messages directly
        # It's used by the main service to display menus
        return False
