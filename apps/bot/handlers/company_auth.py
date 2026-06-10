"""Handler de autenticação de empresa via WhatsApp."""

import structlog

from apps.bot.messages import BOT_MESSAGES
from apps.bot.models import ConversationState
from apps.bot.state_machine import (
    STATE_COMPANY_LOGIN_EMAIL,
    STATE_COMPANY_WAITING_CONFIRMATION,
    STATE_IDLE,
    apply_state_transition,
)
from apps.users.models import UserProfile
from infra.waha.protocols import MessageSender

from .base import BaseHandler

logger = structlog.get_logger(__name__)


class CompanyAuthHandler(BaseHandler):
    """Gerencia fluxo de login de empresa via WhatsApp."""

    def __init__(self, waha_client: MessageSender, company_auth_service, email_dispatcher) -> None:
        super().__init__(waha_client)
        self.company_auth = company_auth_service
        self.email_dispatcher = email_dispatcher

    def _get_conversation_state(self, user: UserProfile) -> ConversationState:
        state, _ = ConversationState.objects.get_or_create(user=user)
        return state

    def start_company_login_flow(self, user: UserProfile, chat_id: str) -> None:
        """Pergunta o email da empresa cadastrado no portal."""
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
        """Recebe email, localiza empresa e envia link de confirmação."""
        email = text.strip().lower()
        profile = self.company_auth.link_company_by_email(user.phone_number, email)

        if profile is None:
            self.send_msg(
                user,
                chat_id,
                self.resolve_message(
                    BOT_MESSAGES.menu.company_login_not_found.key,
                    BOT_MESSAGES.menu.company_login_not_found.text,
                ),
            )
            # Volta para seleção de onboarding (não para idle) para o usuário tentar novamente.
            conv = self._get_conversation_state(user)
            apply_state_transition(conversation_state=conv, next_state=STATE_IDLE)
            return

        self.email_dispatcher.dispatch_company_confirmation_email(profile.id)

        conv = self._get_conversation_state(user)
        apply_state_transition(
            conversation_state=conv,
            next_state=STATE_COMPANY_WAITING_CONFIRMATION,
        )
        self.send_msg(
            user,
            chat_id,
            self.resolve_message(
                BOT_MESSAGES.menu.company_login_email_sent.key,
                BOT_MESSAGES.menu.company_login_email_sent.text,
                email=profile.company.email,
            ),
        )
        logger.info("company_confirmation_email_dispatched", user_id=user.id)

    def handle_company_waiting_confirmation(
        self, user: UserProfile, chat_id: str, text: str
    ) -> bool:
        """Aguarda confirmação via email. Detecta se já foi confirmado."""
        # Recarrega user do banco para pegar is_company_authenticated atualizado.
        fresh = UserProfile.objects.select_related("company").get(pk=user.pk)
        if fresh.is_company_authenticated:
            conv = self._get_conversation_state(user)
            apply_state_transition(
                conversation_state=conv, next_state=STATE_IDLE, clear_flow_data=True
            )
            self.send_msg(
                user,
                chat_id,
                self.resolve_message(
                    BOT_MESSAGES.menu.company_welcome.key,
                    BOT_MESSAGES.menu.company_welcome.text,
                    company_name=fresh.company.nome,
                ),
            )
            return True

        text_lower = text.strip().lower()
        if text_lower == "reenviar":
            ok = self._resend_company_confirmation(user, chat_id)
            if ok:
                self.send_msg(
                    user,
                    chat_id,
                    self.resolve_message(
                        BOT_MESSAGES.menu.company_login_resend_success.key,
                        BOT_MESSAGES.menu.company_login_resend_success.text,
                    ),
                )
            else:
                self.send_msg(
                    user,
                    chat_id,
                    self.resolve_message(
                        BOT_MESSAGES.menu.company_login_resend_error.key,
                        BOT_MESSAGES.menu.company_login_resend_error.text,
                    ),
                )
            return True

        self.send_msg(
            user,
            chat_id,
            self.resolve_message(
                BOT_MESSAGES.menu.company_login_waiting.key,
                BOT_MESSAGES.menu.company_login_waiting.text,
            ),
        )
        return True

    def _resend_company_confirmation(self, user: UserProfile, chat_id: str) -> bool:
        fresh = UserProfile.objects.select_related("company").get(pk=user.pk)
        if fresh.is_company_authenticated or not fresh.company_confirmation_token:
            return False
        self.email_dispatcher.dispatch_company_confirmation_email(fresh.id)
        return True

    def handle(self, user: UserProfile, chat_id: str, text: str) -> bool:
        from apps.bot.state_machine import normalize_current_action

        action = normalize_current_action(self._get_conversation_state(user).current_action)
        if action == STATE_COMPANY_LOGIN_EMAIL:
            self.handle_company_login_email(user, chat_id, text)
            return True
        if action == STATE_COMPANY_WAITING_CONFIRMATION:
            self.handle_company_waiting_confirmation(user, chat_id, text)
            return True
        return False
