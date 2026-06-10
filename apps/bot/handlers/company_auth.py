"""Handler de autenticação de empresa via WhatsApp (email + senha do portal)."""

import structlog

from apps.bot.messages import BOT_MESSAGES
from apps.bot.models import ConversationState
from apps.bot.state_machine import (
    STATE_COMPANY_LOGIN_EMAIL,
    STATE_COMPANY_LOGIN_PASSWORD,
    STATE_IDLE,
    apply_state_transition,
)
from apps.users.models import UserProfile
from infra.waha.protocols import MessageSender

from .base import BaseHandler

logger = structlog.get_logger(__name__)


class CompanyAuthHandler(BaseHandler):
    """Gerencia fluxo de login de empresa via WhatsApp (email + senha)."""

    def __init__(self, waha_client: MessageSender, company_auth_service, email_dispatcher) -> None:
        super().__init__(waha_client)
        self.company_auth = company_auth_service
        self.email_dispatcher = email_dispatcher

    def _get_conversation_state(self, user: UserProfile) -> ConversationState:
        state, _ = ConversationState.objects.get_or_create(user=user)
        return state

    def start_company_login_flow(self, user: UserProfile, chat_id: str) -> None:
        """Pede o e-mail da empresa cadastrado no portal."""
        conv = self._get_conversation_state(user)
        apply_state_transition(
            conversation_state=conv,
            next_state=STATE_COMPANY_LOGIN_EMAIL,
            clear_flow_data=True,
        )
        self.send_msg(
            user,
            chat_id,
            self.resolve_message(
                BOT_MESSAGES.menu.company_login_ask_email.key,
                BOT_MESSAGES.menu.company_login_ask_email.text,
            ),
        )

    def handle_company_login_email(self, user: UserProfile, chat_id: str, text: str) -> None:
        """Valida que a empresa existe e pede a senha."""
        from apps.jobs.models.company import Company

        email = text.strip().lower()
        try:
            Company.objects.get(email=email)
        except Company.DoesNotExist:
            self.send_msg(
                user,
                chat_id,
                self.resolve_message(
                    BOT_MESSAGES.menu.company_login_not_found.key,
                    BOT_MESSAGES.menu.company_login_not_found.text,
                ),
            )
            conv = self._get_conversation_state(user)
            apply_state_transition(conversation_state=conv, next_state=STATE_IDLE)
            return

        conv = self._get_conversation_state(user)
        conv.flow_data = {"company_email": email}
        apply_state_transition(
            conversation_state=conv,
            next_state=STATE_COMPANY_LOGIN_PASSWORD,
            update_fields=["flow_data"],
        )
        self.send_msg(
            user,
            chat_id,
            self.resolve_message(
                BOT_MESSAGES.menu.company_login_ask_password.key,
                BOT_MESSAGES.menu.company_login_ask_password.text,
            ),
        )

    def handle_company_login_password(self, user: UserProfile, chat_id: str, text: str) -> None:
        """Autentica a empresa com a senha e loga diretamente."""
        conv = self._get_conversation_state(user)
        email = (conv.flow_data or {}).get("company_email", "")

        if not email:
            apply_state_transition(
                conversation_state=conv, next_state=STATE_IDLE, clear_flow_data=True
            )
            self.send_msg(user, chat_id, BOT_MESSAGES.menu.unknown_command.text)
            return

        profile = self.company_auth.authenticate_company(user.phone_number, email, text)

        if profile is None:
            self.send_msg(
                user,
                chat_id,
                self.resolve_message(
                    BOT_MESSAGES.menu.company_login_wrong_credentials.key,
                    BOT_MESSAGES.menu.company_login_wrong_credentials.text,
                ),
            )
            return

        apply_state_transition(conversation_state=conv, next_state=STATE_IDLE, clear_flow_data=True)
        self.send_msg(
            user,
            chat_id,
            self.resolve_message(
                BOT_MESSAGES.menu.company_welcome.key,
                BOT_MESSAGES.menu.company_welcome.text,
                company_name=profile.company.nome,
            ),
        )
        logger.info("company_login_success", user_id=user.id, company_id=profile.company_id)

    def handle(self, user: UserProfile, chat_id: str, text: str) -> bool:
        from apps.bot.state_machine import normalize_current_action

        action = normalize_current_action(self._get_conversation_state(user).current_action)
        if action == STATE_COMPANY_LOGIN_EMAIL:
            self.handle_company_login_email(user, chat_id, text)
            return True
        if action == STATE_COMPANY_LOGIN_PASSWORD:
            self.handle_company_login_password(user, chat_id, text)
            return True
        return False
