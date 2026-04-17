"""Refactored bot service using handler pattern and separation of concerns."""
import structlog
from django.conf import settings

from apps.bot.handlers import AuthenticationHandler, JobReviewHandler, JobSearchHandler, MenuHandler
from apps.bot.models import BotConfiguration, InteractionLog
from apps.users.models import UserProfile
from apps.users.services import UTFPRAuthService
from infra.jobspy.service import JobSearchService
from infra.waha.client import WahaClient

logger = structlog.get_logger(__name__)


class BotService:
    """Orchestrates bot conversation flow using specialized handlers.

    Attributes:
        auth_service: UTFPR authentication service instance.
        job_service: Job search service instance.
        waha_client: WAHA client for WhatsApp messaging.
        auth_handler: Authentication handler instance.
        job_handler: Job search handler instance.
        menu_handler: Menu handler instance.
        review_handler: Job review handler instance.
    """

    def __init__(
        self,
        auth_service: UTFPRAuthService | None = None,
        job_service: JobSearchService | None = None,
        waha_client: WahaClient | None = None,
    ) -> None:
        """Initialize bot service with dependencies.

        Args:
            auth_service: Authentication service (optional, will create default).
            job_service: Job search service (optional, will create default).
            waha_client: WAHA client (optional, will create default).
        """
        waha_settings = BotConfiguration.get_active()
        self.auth_service = auth_service or UTFPRAuthService()
        self.job_service = job_service or JobSearchService()
        self.waha_client = waha_client or WahaClient(settings=waha_settings)

        # Initialize handlers
        self.auth_handler = AuthenticationHandler(self.waha_client, self.auth_service)
        self.job_handler = JobSearchHandler(self.waha_client, self.job_service)
        self.menu_handler = MenuHandler(self.waha_client)
        self.review_handler = JobReviewHandler(self.waha_client, self.job_service)

    def process_message(self, chat_id: str, message: str, from_me: bool) -> None:
        """Process incoming WhatsApp message.

        Args:
            chat_id: WhatsApp chat identifier.
            message: Message text.
            from_me: Whether message was sent by the bot.
        """
        # Ignore messages from bot itself
        if from_me:
            return

        # Ignore empty messages
        if not message or not message.strip():
            return

        text = message.strip().lower()

        # Get or create user
        try:
            user = UserProfile.objects.get(phone_number=chat_id)
        except UserProfile.DoesNotExist:
            user = UserProfile.objects.create(phone_number=chat_id)
            logger.info("new_user_created", chat_id=chat_id)

        # Log received message
        self._log_received(user, message)

        # --- GLOBAL COMMANDS (Highest Priority) ---
        if text in {
            "menu",
            "inicio",
            "início",
            "start",
            "começar",
            "oi",
            "ola",
            "olá",
            "bom dia",
            "boa tarde",
            "boa noite",
        }:
            self._reset_state(user)
            self.menu_handler.send_menu(user, chat_id)
            return

        if text in {"cancelar", "voltar", "sair"}:
            if text == "sair" and user.is_authenticated_utfpr:
                self.auth_handler.handle_logout(user, chat_id)
                return

            self._reset_state(user)
            self.waha_client.send_message(chat_id, "✅ Ação cancelada.")
            self.menu_handler.send_menu(user, chat_id)
            return

        if user.current_action == "login_step_waiting_confirmation":
            self.auth_handler.handle_login_waiting_confirmation(user, chat_id, text)
            return

        # --- STATE MACHINE ---
        if user.current_action:
            if self._handle_pending_action(user, chat_id, text):
                return

        # --- MAIN MENU COMMANDS ---
        if text in {"1", "cadastrar", "login", "entrar"}:
            self.auth_handler.start_login_flow(user, chat_id)
            return

        if not user.is_authenticated_utfpr and text in {
            "2",
            "empresa",
            "sou empresa",
            "cadastrar vaga",
            "publicar vaga",
        }:
            user.current_action = "company_onboarding_selection"
            user.flow_data = {}
            user.save(update_fields=["current_action", "flow_data", "last_activity"])
            self.menu_handler.send_company_onboarding_menu(user, chat_id)
            return

        if text in {"2", "logout", "deslogar"}:
            self.auth_handler.handle_logout(user, chat_id)
            return

        if text in {"3", "vagas", "buscar", "cursos"}:
            self.job_handler.start_course_selection(user, chat_id)
            return

        if text in {"4", "review", "vagas da semana"}:
            self.review_handler.send_review(user, chat_id)
            return

        # Unknown command
        self.menu_handler.send_unknown_command(user, chat_id)

    def _handle_pending_action(self, user: UserProfile, chat_id: str, text: str) -> bool:
        """Delegate to appropriate handler based on current action.

        Args:
            user: User profile.
            chat_id: WhatsApp chat ID.
            text: User message.

        Returns:
            True if action was handled, False otherwise.
        """
        # Try authentication handler
        if self.auth_handler.handle(user, chat_id, text):
            return True

        # Try job search handler
        if self.job_handler.handle(user, chat_id, text):
            return True

        if user.current_action == "company_onboarding_selection":
            if text in {"1", "2"}:
                sent = self.menu_handler.send_company_onboarding_links(
                    user,
                    chat_id,
                    text,
                    settings.PORTAL_BASE_URL,
                )
                if not sent:
                    self.waha_client.send_message(
                        chat_id,
                        "⚠️ Portal de empresas temporariamente indisponivel. "
                        "Tente novamente em alguns minutos.",
                    )
                    logger.error(
                        "company_onboarding_portal_unavailable",
                        user_id=user.id,
                        portal_base_url=settings.PORTAL_BASE_URL,
                    )

                self._reset_state(user)
                return True

            self.menu_handler.send_company_onboarding_menu(user, chat_id)
            return True

        return False

    def _reset_state(self, user: UserProfile) -> None:
        """Reset user conversation state.

        Args:
            user: User profile to reset.
        """
        user.current_action = None
        user.flow_data = {}
        user.save(update_fields=["current_action", "flow_data", "last_activity"])

    def _log_received(self, user: UserProfile, message: str) -> None:
        """Log received message to database.

        Args:
            user: User profile.
            message: Message text received.
        """
        try:
            InteractionLog.objects.create(
                user=user,
                message_content=message,
                message_type="RECEIVED",
                session_id=self.waha_client.settings.session_name,
            )
        except Exception as e:
            logger.error(
                "failed_to_log_received_message",
                user_id=user.id,
                error=str(e),
            )
