"""Menu handler for displaying navigation options."""
import structlog

from apps.core.portal_links import build_portal_url
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
                "3️⃣ Buscar Vagas\n"
                "4️⃣ Ver Review de Vagas\n\n"
                "Digite o número da opção desejada."
            )
        else:
            menu_text = (
                f"{self.BRAND_HEADER}\n\n"
                "📋 *Menu Principal*:\n"
                "1️⃣ Fazer Cadastro/Login\n"
                "2️⃣ Sou empresa (cadastrar vaga)\n"
                "3️⃣ Buscar Vagas\n\n"
                "Digite o número da opção desejada."
            )

        self.send_msg(user, chat_id, menu_text)
        logger.info("menu_displayed", user_id=user.id, authenticated=user.is_authenticated_utfpr)

    def send_company_onboarding_menu(self, user: UserProfile, chat_id: str) -> None:
        """Send company onboarding menu.

        Args:
            user: User profile.
            chat_id: WhatsApp chat ID.
        """
        menu_text = (
            f"{self.BRAND_HEADER}\n\n"
            "🏢 *Onboarding para Empresas*\n\n"
            "1️⃣ Cadastrar empresa\n"
            "2️⃣ Ja tenho conta / publicar vaga\n\n"
            "Digite 1 ou 2 para continuar."
        )
        self.send_msg(user, chat_id, menu_text)

    def send_company_onboarding_links(
        self,
        user: UserProfile,
        chat_id: str,
        option: str,
        portal_base_url: str,
    ) -> bool:
        """Send company onboarding links based on user selection.

        Args:
            user: User profile.
            chat_id: WhatsApp chat ID.
            option: "1" for signup, "2" for login.
            portal_base_url: Base URL of the company portal.

        Returns:
            True if links were sent successfully, False if URL construction failed.
        """
        if option == "1":
            signup_url = build_portal_url(portal_base_url, "/empresas/signup/")
            if signup_url is None:
                return False

            msg = (
                "✅ *Cadastro de Empresa*\n\n"
                f"1) Crie sua conta: {signup_url}\n"
                "2) Confirme os dados da empresa\n"
                "3) Entre no portal para publicar sua primeira vaga"
            )
            self.send_msg(user, chat_id, msg)
            return True

        if option == "2":
            login_url = build_portal_url(portal_base_url, "/empresas/login/")
            new_job_url = build_portal_url(portal_base_url, "/empresas/vagas/nova/")
            if login_url is None or new_job_url is None:
                return False

            msg = (
                "✅ *Publicar Vaga*\n\n"
                f"Acesse sua conta: {login_url}\n"
                f"Nova vaga: {new_job_url}"
            )
            self.send_msg(user, chat_id, msg)
            return True

        return False

    def send_unknown_command(self, user: UserProfile, chat_id: str) -> None:
        """
        Send unknown command message.

        Args:
            user: User profile
            chat_id: WhatsApp chat ID
        """
        msg = self.get_text(
            "unknown_command",
            "❓ Comando não reconhecido.\n\n" "Digite *menu* para ver as opções disponíveis.",
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
