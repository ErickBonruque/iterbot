"""Authentication handler for login/logout flows."""
import structlog

from apps.users.models import UserProfile
from apps.users.services import UTFPRAuthService

from .base import BaseHandler

logger = structlog.get_logger(__name__)


class AuthenticationHandler(BaseHandler):
    """Handles user authentication (login/logout) flows."""

    def __init__(self, waha_client, auth_service: UTFPRAuthService) -> None:
        """
        Initialize authentication handler.
        
        Args:
            waha_client: WAHA client for messaging
            auth_service: Service for UTFPR authentication
        """
        super().__init__(waha_client)
        self.auth_service = auth_service

    def start_login_flow(self, user: UserProfile, chat_id: str) -> None:
        """
        Start login flow by requesting RA.
        
        Args:
            user: User profile
            chat_id: WhatsApp chat ID
        """
        if user.is_authenticated_utfpr:
            self.send_msg(
                user,
                chat_id,
                "✅ Você já está cadastrado! Selecione a opção 3 para buscar vagas.",
            )
            return

        user.current_action = "login_step_ra"
        user.flow_data = {}
        user.save(update_fields=["current_action", "flow_data", "last_activity"])

        msg = self.get_text(
            "login_prompt_ra",
            "🔐 *Cadastro UTFPR*\n\n"
            "Por favor, digite seu **RA** (ex: a1234567):\n\n"
            "_(Digite 'cancelar' para voltar)_",
        )
        self.send_msg(user, chat_id, msg)

    def handle_login_ra(self, user: UserProfile, chat_id: str, text: str) -> None:
        """
        Handle RA input during login.
        
        Args:
            user: User profile
            chat_id: WhatsApp chat ID
            text: User input (RA)
        """
        ra = text.strip().lower()

        if len(ra) < 5:
            self.send_msg(
                user, chat_id, "❌ RA muito curto. Tente novamente ou digite 'cancelar'."
            )
            return

        user.flow_data["temp_ra"] = ra
        user.current_action = "login_step_password"
        user.save(update_fields=["current_action", "flow_data", "last_activity"])

        msg = self.get_text(
            "login_prompt_password",
            "🔑 Agora digite sua **Senha** do Portal do Aluno:\n\n"
            "_(Seus dados são criptografados e usados apenas para validação)_",
        )
        self.send_msg(user, chat_id, msg)

    def handle_login_password(
        self, user: UserProfile, chat_id: str, text: str
    ) -> bool:
        """
        Handle password input and complete authentication.
        
        Args:
            user: User profile
            chat_id: WhatsApp chat ID
            text: User input (password)
            
        Returns:
            True if authentication succeeded
        """
        password = text.strip()
        ra = user.flow_data.get("temp_ra")

        if not ra:
            self.send_msg(
                user, chat_id, "❌ Erro de fluxo. Por favor, comece novamente."
            )
            self.reset_state(user)
            return False

        self.send_msg(user, chat_id, "🔄 Validando credenciais...")

        if self.auth_service.authenticate(ra, password):
            self.auth_service.link_user(chat_id, ra, password)
            self.reset_state(user)

            msg = self.get_text(
                "login_success",
                "✅ **Cadastro Confirmado!**\n\n"
                "Agora você pode buscar vagas personalizadas para seu curso.\n\n"
                "Escolha a opção 3 no menu.",
            )
            self.send_msg(user, chat_id, msg)
            
            logger.info("user_authenticated", user_id=user.id, ra=ra)
            return True
        else:
            msg = self.get_text(
                "login_error",
                "❌ **Falha no login.**\n"
                "RA ou senha incorretos.\n\n"
                "Tente digitar a senha novamente ou digite 'cancelar' para sair.",
            )
            self.send_msg(user, chat_id, msg)
            
            logger.warning("authentication_failed", user_id=user.id, ra=ra)
            return False

    def handle_logout(self, user: UserProfile, chat_id: str) -> None:
        """
        Handle user logout.
        
        Args:
            user: User profile
            chat_id: WhatsApp chat ID
        """
        self.auth_service.logout(chat_id)
        self.send_msg(user, chat_id, "🔒 Você saiu do sistema. Até logo!")
        
        user.current_action = None
        user.selected_course = None
        user.selected_term = None
        user.save(
            update_fields=[
                "current_action",
                "selected_course",
                "selected_term",
                "last_activity",
            ]
        )
        
        logger.info("user_logged_out", user_id=user.id)

    def reset_state(self, user: UserProfile) -> None:
        """
        Reset user conversation state.
        
        Args:
            user: User profile to reset
        """
        user.current_action = None
        user.flow_data = {}
        user.save(update_fields=["current_action", "flow_data", "last_activity"])

    def handle(self, user: UserProfile, chat_id: str, text: str) -> bool:
        """
        Handle authentication-related messages.
        
        Args:
            user: User profile
            chat_id: WhatsApp chat ID
            text: User message
            
        Returns:
            True if message was handled
        """
        action = user.current_action

        if action == "login_step_ra":
            self.handle_login_ra(user, chat_id, text)
            return True
        elif action == "login_step_password":
            self.handle_login_password(user, chat_id, text)
            return True

        return False
