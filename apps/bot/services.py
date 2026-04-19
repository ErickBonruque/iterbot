"""Refactored bot service using handler pattern and separation of concerns."""

import structlog
from django.conf import settings

from apps.bot.handlers import AuthenticationHandler, JobReviewHandler, JobSearchHandler, MenuHandler
from apps.bot.messages import BOT_MESSAGES
from apps.bot.models import BotConfiguration, ConversationState, InteractionLog
from apps.bot.tasks import send_confirmation_email
from apps.users.models import UserProfile
from apps.users.services import UTFPRAuthService
from infra.jobspy.service import JobSearchService
from infra.waha.client import WahaClient
from infra.waha.protocols import (
    Authenticator,
    EmailConfirmationDispatcher,
    JobSearcher,
    MessageSender,
)

logger = structlog.get_logger(__name__)


class CeleryEmailConfirmationDispatcher:
    """Adapter that dispatches confirmation email via Celery task."""

    def dispatch_confirmation_email(self, user_id: int) -> None:
        send_confirmation_email.delay(user_id)


class BotService:
    """Orchestrates bot conversation flow using specialized handlers."""

    def __init__(
        self,
        auth_service: Authenticator | None = None,
        job_service: JobSearcher | None = None,
        waha_client: MessageSender | None = None,
        email_dispatcher: EmailConfirmationDispatcher | None = None,
    ) -> None:
        waha_settings = BotConfiguration.get_active()
        self.auth_service = auth_service or UTFPRAuthService()
        self.job_service = job_service or JobSearchService()
        self.waha_client = waha_client or WahaClient(settings=waha_settings)
        self.email_dispatcher = email_dispatcher or CeleryEmailConfirmationDispatcher()

        self.auth_handler = AuthenticationHandler(
            self.waha_client,
            self.auth_service,
            self.email_dispatcher,
        )
        self.job_handler = JobSearchHandler(self.waha_client, self.job_service)
        self.menu_handler = MenuHandler(self.waha_client)
        self.review_handler = JobReviewHandler(self.waha_client, self.job_service)

    def process_message(self, chat_id: str, message: str, from_me: bool) -> None:
        if from_me:
            return

        if not message or not message.strip():
            return

        text = message.strip().lower()

        try:
            user = UserProfile.objects.get(phone_number=chat_id)
        except UserProfile.DoesNotExist:
            user = UserProfile.objects.create(phone_number=chat_id)
            logger.info("new_user_created", chat_id=chat_id)

        conversation_state = self._get_conversation_state(user)
        self._log_received(user, message)

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
            self.waha_client.send_message(
                chat_id,
                self.auth_handler.resolve_message(
                    "system.action_cancelled",
                    BOT_MESSAGES.system.action_cancelled.text,
                ),
            )
            self.menu_handler.send_menu(user, chat_id)
            return

        if conversation_state.current_action == "login_step_waiting_confirmation":
            self.auth_handler.handle_login_waiting_confirmation(user, chat_id, text)
            return

        if conversation_state.current_action and self._handle_pending_action(user, chat_id, text):
            return

        self._handle_main_menu_command(user, chat_id, text)

    def _handle_main_menu_command(self, user: "UserProfile", chat_id: str, text: str) -> None:
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
            conversation_state = self._get_conversation_state(user)
            conversation_state.current_action = "company_onboarding_selection"
            conversation_state.flow_data = {}
            conversation_state.save(update_fields=["current_action", "flow_data", "updated_at"])
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

        self.menu_handler.send_unknown_command(user, chat_id)

    def _handle_pending_action(self, user: UserProfile, chat_id: str, text: str) -> bool:
        if self.auth_handler.handle(user, chat_id, text):
            return True

        if self.job_handler.handle(user, chat_id, text):
            return True

        conversation_state = self._get_conversation_state(user)
        if conversation_state.current_action == "company_onboarding_selection":
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
                        self.auth_handler.resolve_message(
                            "system.portal_unavailable",
                            BOT_MESSAGES.system.portal_unavailable.text,
                        ),
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
        conversation_state = self._get_conversation_state(user)
        conversation_state.current_action = None
        conversation_state.flow_data = {}
        conversation_state.save(update_fields=["current_action", "flow_data", "updated_at"])

    def _get_conversation_state(self, user: UserProfile) -> ConversationState:
        conversation_state, _ = ConversationState.objects.get_or_create(user=user)
        return conversation_state

    def _session_name(self) -> str:
        settings_obj = getattr(self.waha_client, "settings", None)
        return getattr(settings_obj, "session_name", "unknown")

    def _log_received(self, user: UserProfile, message: str) -> None:
        try:
            InteractionLog.objects.create(
                user=user,
                message_content=message,
                message_type="RECEIVED",
                session_id=self._session_name(),
            )
        except Exception as e:
            logger.error(
                "failed_to_log_received_message",
                user_id=user.id,
                error=str(e),
            )
