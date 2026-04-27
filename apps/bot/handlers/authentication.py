"""Authentication handler for login/logout flows."""

import structlog
from django.core.exceptions import ValidationError

from apps.bot.messages import BOT_MESSAGES
from apps.bot.models import ConversationState
from apps.bot.state_machine import (
    STATE_IDLE,
    STATE_LOGIN_STEP_EMAIL,
    STATE_LOGIN_STEP_PASSWORD,
    STATE_LOGIN_STEP_RA,
    STATE_LOGIN_STEP_WAITING_CONFIRMATION,
    apply_state_transition,
    is_waiting_confirmation,
    normalize_current_action,
)
from apps.users.models import UserProfile
from apps.users.validators import validate_utfpr_email
from infra.waha.protocols import Authenticator, EmailConfirmationDispatcher, MessageSender

from .base import BaseHandler

logger = structlog.get_logger(__name__)


class AuthenticationHandler(BaseHandler):
    """Handles user authentication (login/logout) flows."""

    def __init__(
        self,
        waha_client: MessageSender,
        auth_service: Authenticator,
        email_dispatcher: EmailConfirmationDispatcher,
    ) -> None:
        super().__init__(waha_client)
        self.auth_service = auth_service
        self.email_dispatcher = email_dispatcher

    def _get_conversation_state(self, user: UserProfile) -> ConversationState:
        conversation_state, _ = ConversationState.objects.get_or_create(user=user)
        return conversation_state

    def start_login_flow(self, user: UserProfile, chat_id: str) -> None:
        if user.is_authenticated_utfpr:
            self.send_msg(
                user,
                chat_id,
                self.resolve_message(
                    BOT_MESSAGES.auth.login_already_registered.key,
                    BOT_MESSAGES.auth.login_already_registered.text,
                ),
            )
            return

        conversation_state = self._get_conversation_state(user)
        if is_waiting_confirmation(conversation_state.current_action):
            self.handle_login_waiting_confirmation(user, chat_id, "")
            return

        apply_state_transition(
            conversation_state=conversation_state,
            next_state=STATE_LOGIN_STEP_RA,
            clear_flow_data=True,
        )

        self.send_msg(
            user,
            chat_id,
            self.resolve_message(
                BOT_MESSAGES.auth.login_prompt_ra.key,
                BOT_MESSAGES.auth.login_prompt_ra.text,
            ),
        )

    def handle_login_ra(self, user: UserProfile, chat_id: str, text: str) -> None:
        ra = text.strip().lower()

        if len(ra) < 5:
            self.send_msg(
                user,
                chat_id,
                self.resolve_message(
                    BOT_MESSAGES.auth.login_ra_too_short.key,
                    BOT_MESSAGES.auth.login_ra_too_short.text,
                ),
            )
            return

        conversation_state = self._get_conversation_state(user)
        conversation_state.flow_data["temp_ra"] = ra
        apply_state_transition(
            conversation_state=conversation_state,
            next_state=STATE_LOGIN_STEP_PASSWORD,
            update_fields=["flow_data"],
        )

        self.send_msg(
            user,
            chat_id,
            self.resolve_message(
                BOT_MESSAGES.auth.login_prompt_password.key,
                BOT_MESSAGES.auth.login_prompt_password.text,
            ),
        )

    def handle_login_password(self, user: UserProfile, chat_id: str, text: str) -> bool:
        password = text.strip()
        conversation_state = self._get_conversation_state(user)
        ra = conversation_state.flow_data.get("temp_ra")

        if not ra:
            self.send_msg(
                user,
                chat_id,
                self.resolve_message(
                    BOT_MESSAGES.auth.login_flow_error.key,
                    BOT_MESSAGES.auth.login_flow_error.text,
                ),
            )
            self.reset_state(user)
            return False

        self.send_msg(
            user,
            chat_id,
            self.resolve_message(
                BOT_MESSAGES.auth.login_validating_credentials.key,
                BOT_MESSAGES.auth.login_validating_credentials.text,
            ),
        )

        if self.auth_service.authenticate(ra, password):
            # Re-login direto: se já existe perfil com este phone e e-mail
            # verificado, pula a etapa de e-mail e a confirmação. Sem esse
            # short-circuit, o usuário precisaria redigitar o e-mail e o
            # link_user só decidiria pelo welcome_back depois disso.
            existing = UserProfile.objects.filter(phone_number=chat_id).first()
            if existing and existing.email_verified and existing.email:
                linked_user = self.auth_service.link_user(
                    chat_id, ra, password, existing.email
                )
                if linked_user and linked_user.email_verified and linked_user.is_authenticated_utfpr:
                    apply_state_transition(
                        conversation_state=conversation_state,
                        next_state=STATE_IDLE,
                        clear_flow_data=True,
                    )
                    self.send_msg(
                        user,
                        chat_id,
                        self.resolve_message(
                            BOT_MESSAGES.auth.login_welcome_back.key,
                            BOT_MESSAGES.auth.login_welcome_back.text,
                            email=existing.email,
                        ),
                    )
                    logger.info("user_relogged_in_skipping_email_step", user_id=linked_user.id)
                    return True

            conversation_state.flow_data["temp_password"] = password
            apply_state_transition(
                conversation_state=conversation_state,
                next_state=STATE_LOGIN_STEP_EMAIL,
                update_fields=["flow_data"],
            )

            self.send_msg(
                user,
                chat_id,
                self.resolve_message(
                    BOT_MESSAGES.auth.login_prompt_email.key,
                    BOT_MESSAGES.auth.login_prompt_email.text,
                ),
            )
            return True

        self.send_msg(
            user,
            chat_id,
            self.resolve_message(
                BOT_MESSAGES.auth.login_error.key,
                BOT_MESSAGES.auth.login_error.text,
            ),
        )
        logger.warning("authentication_failed", user_id=user.id, ra=ra)
        return False

    def handle_login_email(self, user: UserProfile, chat_id: str, text: str) -> bool:
        email = text.strip().lower()

        if len(email) < 10:
            self.send_msg(
                user,
                chat_id,
                self.resolve_message(
                    BOT_MESSAGES.auth.login_email_too_short.key,
                    BOT_MESSAGES.auth.login_email_too_short.text,
                ),
            )
            return True

        try:
            validate_utfpr_email(email)
        except ValidationError:
            self.send_msg(
                user,
                chat_id,
                self.resolve_message(
                    BOT_MESSAGES.auth.login_email_invalid.key,
                    BOT_MESSAGES.auth.login_email_invalid.text,
                ),
            )
            return True

        conversation_state = self._get_conversation_state(user)
        ra = conversation_state.flow_data.get("temp_ra")
        password = conversation_state.flow_data.get("temp_password")

        if not ra or not password:
            self.send_msg(
                user,
                chat_id,
                self.resolve_message(
                    BOT_MESSAGES.auth.login_flow_error.key,
                    BOT_MESSAGES.auth.login_flow_error.text,
                ),
            )
            self.reset_state(user)
            return False

        linked_user = self.auth_service.link_user(chat_id, ra, password, email)

        if linked_user:
            # Re-login: e-mail já verificado anteriormente — autentica direto sem reenviar link.
            if linked_user.email_verified and linked_user.is_authenticated_utfpr:
                apply_state_transition(
                    conversation_state=conversation_state,
                    next_state=STATE_IDLE,
                    clear_flow_data=True,
                )
                self.send_msg(
                    user,
                    chat_id,
                    self.resolve_message(
                        BOT_MESSAGES.auth.login_welcome_back.key,
                        BOT_MESSAGES.auth.login_welcome_back.text,
                        email=email,
                    ),
                )
                logger.info("user_relogged_in", user_id=linked_user.id)
                return True

            # Primeiro cadastro (ou e-mail novo): dispara verificação por link.
            apply_state_transition(
                conversation_state=conversation_state,
                next_state=STATE_LOGIN_STEP_WAITING_CONFIRMATION,
            )
            self.email_dispatcher.dispatch_confirmation_email(linked_user.id)
            self.send_msg(
                user,
                chat_id,
                self.resolve_message(
                    BOT_MESSAGES.auth.login_waiting_confirmation.key,
                    BOT_MESSAGES.auth.login_waiting_confirmation.text,
                    email=email,
                ),
            )
            return True

        self.send_msg(
            user,
            chat_id,
            self.resolve_message(
                BOT_MESSAGES.auth.login_flow_error.key,
                BOT_MESSAGES.auth.login_flow_error.text,
            ),
        )
        self.reset_state(user)
        return False

    def handle_login_waiting_confirmation(self, user: UserProfile, chat_id: str, text: str) -> bool:
        text_lower = text.strip().lower()

        if text_lower == "reenviar":
            if self.auth_service.resend_confirmation(chat_id):
                self.send_msg(
                    user,
                    chat_id,
                    self.resolve_message(
                        BOT_MESSAGES.auth.login_resend_success.key,
                        BOT_MESSAGES.auth.login_resend_success.text,
                    ),
                )
            else:
                self.send_msg(
                    user,
                    chat_id,
                    self.resolve_message(
                        BOT_MESSAGES.auth.login_resend_error.key,
                        BOT_MESSAGES.auth.login_resend_error.text,
                    ),
                )
            return True

        self.send_msg(
            user,
            chat_id,
            self.resolve_message(
                BOT_MESSAGES.auth.login_waiting_status.key,
                BOT_MESSAGES.auth.login_waiting_status.text,
            ),
        )
        return True

    def handle_logout(self, user: UserProfile, chat_id: str) -> None:
        self.auth_service.logout(chat_id)
        self.send_msg(
            user,
            chat_id,
            self.resolve_message(
                BOT_MESSAGES.auth.logout_success.key,
                BOT_MESSAGES.auth.logout_success.text,
            ),
        )

        conversation_state = self._get_conversation_state(user)
        conversation_state.selected_course = None
        conversation_state.selected_term = None
        apply_state_transition(
            conversation_state=conversation_state,
            next_state=STATE_IDLE,
            update_fields=["selected_course", "selected_term"],
        )

        logger.info("user_logged_out", user_id=user.id)

    def reset_state(self, user: UserProfile) -> None:
        conversation_state = self._get_conversation_state(user)
        apply_state_transition(
            conversation_state=conversation_state,
            next_state=STATE_IDLE,
            clear_flow_data=True,
        )

    def handle(self, user: UserProfile, chat_id: str, text: str) -> bool:
        action = normalize_current_action(self._get_conversation_state(user).current_action)

        if action == STATE_LOGIN_STEP_RA:
            self.handle_login_ra(user, chat_id, text)
            return True
        if action == STATE_LOGIN_STEP_PASSWORD:
            self.handle_login_password(user, chat_id, text)
            return True
        if action == STATE_LOGIN_STEP_EMAIL:
            self.handle_login_email(user, chat_id, text)
            return True
        if action == STATE_LOGIN_STEP_WAITING_CONFIRMATION:
            self.handle_login_waiting_confirmation(user, chat_id, text)
            return True

        return False
