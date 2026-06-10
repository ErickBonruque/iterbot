"""Refactored bot service using handler pattern and separation of concerns."""

import time

import structlog
from django.conf import settings

from apps.bot.handlers import (
    AuthenticationHandler,
    CompanyAuthHandler,
    JobReviewHandler,
    JobSearchHandler,
    MenuHandler,
)
from apps.bot.messages import BOT_MESSAGES
from apps.bot.models import BotConfiguration, ConversationState, InteractionLog
from apps.bot.state_machine import (
    ROUTE_COMPANY,
    STATE_COMPANY_ONBOARDING_SELECTION,
    STATE_COMPANY_WAITING_CONFIRMATION,
    STATE_IDLE,
    apply_state_transition,
    has_active_flow,
    is_waiting_confirmation,
    normalize_current_action,
    route_for_action,
)
from apps.bot.tasks import CeleryEmailConfirmationDispatcher
from apps.companies.company_auth_service import CompanyAuthService
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
        self.email_dispatcher = email_dispatcher or CeleryEmailConfirmationDispatcher()
        self.auth_service = auth_service or UTFPRAuthService(email_dispatcher=self.email_dispatcher)
        self.company_auth_service = CompanyAuthService()
        self.job_service = job_service or JobSearchService()
        self.waha_client = waha_client or WahaClient(settings=waha_settings)

        self.auth_handler = AuthenticationHandler(
            self.waha_client,
            self.auth_service,
            self.email_dispatcher,
        )
        self.company_auth_handler = CompanyAuthHandler(
            self.waha_client,
            self.company_auth_service,
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
        start = time.time()

        try:
            user = UserProfile.objects.select_related("company").get(phone_number=chat_id)
        except UserProfile.DoesNotExist:
            user = UserProfile.objects.create(phone_number=chat_id)
            logger.info("new_user_created", chat_id=chat_id)

        conversation_state = self._get_conversation_state(user)
        self._log_received(user, message)

        try:
            self._dispatch(user, chat_id, text, conversation_state)

            from apps.bot.models.bot_action_log import BotActionLog

            BotActionLog.objects.create(
                user=user,
                action_type="MENU",
                status="SUCCESS",
                duration_ms=int((time.time() - start) * 1000),
            )
        except Exception as e:
            from apps.bot.models.bot_action_log import BotActionLog

            BotActionLog.objects.create(
                user=user,
                action_type="MENU",
                status="ERROR",
                error_type="EXCEPTION",
                error_message=str(e),
                duration_ms=int((time.time() - start) * 1000),
            )
            logger.error("process_message_exception", chat_id=chat_id, error=str(e), exc_info=True)
            raise

    _GREETINGS = frozenset(
        {
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
        }
    )

    def _dispatch(
        self, user: UserProfile, chat_id: str, text: str, conversation_state: ConversationState
    ) -> None:
        if text in self._GREETINGS:
            self._reset_state(user)
            self.menu_handler.send_menu(user, chat_id)
        elif text in {"cancelar", "voltar"}:
            self._reset_state(user)
            self.waha_client.send_message(
                chat_id,
                self.auth_handler.resolve_message(
                    "system.action_cancelled",
                    BOT_MESSAGES.system.action_cancelled.text,
                ),
            )
            self.menu_handler.send_menu(user, chat_id)
        elif text == "sair":
            self._handle_sair(user, chat_id)
        elif text == "aluno":
            self._handle_switch_to_student(user, chat_id)
        elif is_waiting_confirmation(conversation_state.current_action):
            self.auth_handler.handle_login_waiting_confirmation(user, chat_id, text)
        elif (
            normalize_current_action(conversation_state.current_action)
            == STATE_COMPANY_WAITING_CONFIRMATION
        ):
            self.company_auth_handler.handle_company_waiting_confirmation(user, chat_id, text)
        elif has_active_flow(conversation_state.current_action) and self._handle_pending_action(
            user, chat_id, text
        ):
            pass
        else:
            self._handle_main_menu_command(user, chat_id, text)

    _ALIAS_LOGIN = frozenset({"cadastrar", "login", "entrar"})
    _ALIAS_COMPANY = frozenset({"empresa", "sou empresa", "cadastrar vaga", "publicar vaga"})
    _ALIAS_LOGOUT = frozenset({"logout", "deslogar", "sair da conta"})
    _ALIAS_SEARCH = frozenset({"vagas", "buscar", "cursos"})
    _ALIAS_REVIEW = frozenset({"review", "vagas da semana"})
    _ALIAS_CHANGE_COURSE = frozenset({"trocar curso", "mudar curso", "alterar curso"})

    def _handle_sair(self, user: UserProfile, chat_id: str) -> None:
        """'sair' desloga a sessão ativa: empresa tem prioridade, depois aluno."""
        fresh = UserProfile.objects.select_related("company").get(pk=user.pk)
        if fresh.is_company_authenticated:
            self.company_auth_service.logout_company(chat_id)
            self.waha_client.send_message(
                chat_id,
                self.menu_handler.resolve_message(
                    BOT_MESSAGES.menu.company_logout_success.key,
                    BOT_MESSAGES.menu.company_logout_success.text,
                ),
            )
            self._reset_state(user)
            self.menu_handler.send_menu(user, chat_id)
        elif fresh.is_authenticated_utfpr:
            self.auth_handler.handle_logout(user, chat_id)
        else:
            self._reset_state(user)
            self.menu_handler.send_menu(user, chat_id)

    def _handle_switch_to_student(self, user: UserProfile, chat_id: str) -> None:
        """Switch explícito para modo aluno (útil quando os dois modos estão ativos)."""
        fresh = UserProfile.objects.get(pk=user.pk)
        if fresh.is_authenticated_utfpr:
            # Temporariamente desloga empresa para exibir menu de aluno.
            if fresh.is_company_authenticated:
                self.company_auth_service.logout_company(chat_id)
            self._reset_state(user)
            # Recarrega user para send_menu pegar is_company_authenticated=False.
            user_reloaded = UserProfile.objects.select_related("company").get(pk=user.pk)
            self.menu_handler.send_menu(user_reloaded, chat_id)
        else:
            self.menu_handler.send_unknown_command(user, chat_id)

    def _handle_main_menu_command(self, user: UserProfile, chat_id: str, text: str) -> None:
        if self._handle_text_alias(user, chat_id, text):
            return

        fresh = UserProfile.objects.select_related("company").get(pk=user.pk)

        if fresh.is_company_authenticated:
            handled = self._handle_numeric_company(fresh, chat_id, text)
        elif fresh.is_authenticated_utfpr:
            handled = self._handle_numeric_authenticated(fresh, chat_id, text)
        else:
            handled = self._handle_numeric_unauthenticated(fresh, chat_id, text)

        if not handled:
            self.menu_handler.send_unknown_command(user, chat_id)

    def _handle_text_alias(self, user: UserProfile, chat_id: str, text: str) -> bool:
        if text in self._ALIAS_LOGIN:
            self.auth_handler.start_login_flow(user, chat_id)
            return True
        if text in self._ALIAS_COMPANY:
            self._start_company_onboarding(user, chat_id)
            return True
        if text in self._ALIAS_LOGOUT:
            self._handle_sair(user, chat_id)
            return True
        if text in self._ALIAS_SEARCH:
            self.job_handler.start_course_selection(user, chat_id)
            return True
        if text in self._ALIAS_REVIEW:
            self.review_handler.send_review(user, chat_id)
            return True
        if text in self._ALIAS_CHANGE_COURSE:
            self.job_handler.start_course_change(user, chat_id)
            return True
        return False

    def _handle_numeric_company(self, user: UserProfile, chat_id: str, text: str) -> bool:
        """Menu empresa autenticada: 1=Vagas | 2=Portal | 3=Nova vaga | 0=Sair."""
        if text == "1":
            self.menu_handler.send_company_jobs(user, chat_id)
            return True
        if text == "2":
            self.menu_handler.send_company_portal_link(user, chat_id, settings.PORTAL_BASE_URL)
            return True
        if text == "3":
            self.menu_handler.send_company_new_job_link(user, chat_id, settings.PORTAL_BASE_URL)
            return True
        if text == "0":
            self._handle_sair(user, chat_id)
            return True
        return False

    def _handle_numeric_authenticated(self, user: UserProfile, chat_id: str, text: str) -> bool:
        # Menu autenticado: 1=Buscar | 2=Review | 3=Logout | 4=Trocar Curso | 5=Empresa (se vinculada)
        if text == "1":
            self.job_handler.start_course_selection(user, chat_id)
            return True
        if text == "2":
            self.review_handler.send_review(user, chat_id)
            return True
        if text == "3":
            self.auth_handler.handle_logout(user, chat_id)
            return True
        if text == "4":
            self.job_handler.start_course_change(user, chat_id)
            return True
        if text == "5" and user.company is not None:
            # Switch para modo empresa (re-autentica empresa sem e-mail)
            self.company_auth_service.reauth_company(user.phone_number)
            self._reset_state(user)
            user_reloaded = UserProfile.objects.select_related("company").get(pk=user.pk)
            self.menu_handler.send_menu(user_reloaded, chat_id)
            return True
        return False

    def _handle_numeric_unauthenticated(self, user: UserProfile, chat_id: str, text: str) -> bool:
        # Menu não autenticado: 1=Cadastro/Login de aluno | 2=Cadastro/Login de empresa
        if text == "1":
            self.auth_handler.start_login_flow(user, chat_id)
            return True
        if text == "2":
            self._start_company_onboarding(user, chat_id)
            return True
        return False

    def _start_company_onboarding(self, user: UserProfile, chat_id: str) -> None:
        fresh = UserProfile.objects.select_related("company").get(pk=user.pk)

        # Já autenticado → mostra menu empresa diretamente.
        if fresh.is_company_authenticated:
            self._reset_state(user)
            self.menu_handler.send_menu(fresh, chat_id)
            return

        # Empresa já vinculada mas sessão encerrada → re-autentica sem e-mail.
        if fresh.company is not None:
            self.company_auth_service.reauth_company(fresh.phone_number)
            self._reset_state(user)
            fresh_reloaded = UserProfile.objects.select_related("company").get(pk=user.pk)
            msg = self.menu_handler.resolve_message(
                BOT_MESSAGES.menu.company_reauth_success.key,
                BOT_MESSAGES.menu.company_reauth_success.text,
                company_name=fresh.company.nome,
            )
            self.waha_client.send_message(chat_id, msg)
            self.menu_handler.send_menu(fresh_reloaded, chat_id)
            return

        # Primeiro acesso → fluxo de onboarding (criar conta ou entrar).
        conversation_state = self._get_conversation_state(user)
        apply_state_transition(
            conversation_state=conversation_state,
            next_state=STATE_COMPANY_ONBOARDING_SELECTION,
            clear_flow_data=True,
        )
        self.menu_handler.send_company_onboarding_menu(user, chat_id)

    def _handle_pending_action(self, user: UserProfile, chat_id: str, text: str) -> bool:
        if self.auth_handler.handle(user, chat_id, text):
            return True

        if self.company_auth_handler.handle(user, chat_id, text):
            return True

        if self.job_handler.handle(user, chat_id, text):
            return True

        conversation_state = self._get_conversation_state(user)
        if route_for_action(conversation_state.current_action) == ROUTE_COMPANY:
            action = normalize_current_action(conversation_state.current_action)

            if action == STATE_COMPANY_ONBOARDING_SELECTION:
                if text == "1":
                    sent = self.menu_handler.send_company_onboarding_signup_link(
                        user, chat_id, settings.PORTAL_BASE_URL
                    )
                    if not sent:
                        self.waha_client.send_message(
                            chat_id,
                            self.auth_handler.resolve_message(
                                "system.portal_unavailable",
                                BOT_MESSAGES.system.portal_unavailable.text,
                            ),
                        )
                    self._reset_state(user)
                    return True

                if text == "2":
                    self.company_auth_handler.start_company_login_flow(user, chat_id)
                    return True

                self.menu_handler.send_company_onboarding_menu(user, chat_id)
                return True

        return False

    def _reset_state(self, user: UserProfile) -> None:
        conversation_state = self._get_conversation_state(user)
        apply_state_transition(
            conversation_state=conversation_state,
            next_state=STATE_IDLE,
            clear_flow_data=True,
        )

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
