"""Authentication handler for login/logout flows."""

import structlog
from django.core.exceptions import ValidationError

from apps.bot.messages import BOT_MESSAGES
from apps.bot.models import ConversationState
from apps.users.models import UserProfile
from apps.users.services import UTFPRAuthService
from apps.users.validators import validate_utfpr_email

from .base import BaseHandler

logger = structlog.get_logger(__name__)


class AuthenticationHandler(BaseHandler):
    """Handles user authentication (login/logout) flows."""

    def __init__(self, waha_client, auth_service: UTFPRAuthService) -> None:
        super().__init__(waha_client)
        self.auth_service = auth_service

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
        if conversation_state.current_action == "login_step_waiting_confirmation":
            self.handle_login_waiting_confirmation(user, chat_id, "")
            return

        conversation_state.current_action = "login_step_ra"
        conversation_state.flow_data = {}
        conversation_state.save(update_fields=["current_action", "flow_data", "updated_at"])

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
        conversation_state.current_action = "login_step_password"
        conversation_state.save(update_fields=["current_action", "flow_data", "updated_at"])

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
            conversation_state.flow_data["temp_password"] = password
            conversation_state.current_action = "login_step_email"
            conversation_state.save(update_fields=["current_action", "flow_data", "updated_at"])

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
            conversation_state.current_action = "login_step_waiting_confirmation"
            conversation_state.save(update_fields=["current_action", "updated_at"])

            from apps.bot.tasks import send_confirmation_email

            send_confirmation_email.delay(linked_user.id)
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
        conversation_state.current_action = None
        conversation_state.selected_course = None
        conversation_state.selected_term = None
        conversation_state.save(
            update_fields=["current_action", "selected_course", "selected_term", "updated_at"]
        )

        logger.info("user_logged_out", user_id=user.id)

    def reset_state(self, user: UserProfile) -> None:
        conversation_state = self._get_conversation_state(user)
        conversation_state.current_action = None
        conversation_state.flow_data = {}
        conversation_state.save(update_fields=["current_action", "flow_data", "updated_at"])

    def handle(self, user: UserProfile, chat_id: str, text: str) -> bool:
        action = self._get_conversation_state(user).current_action

        if action == "login_step_ra":
            self.handle_login_ra(user, chat_id, text)
            return True
        if action == "login_step_password":
            self.handle_login_password(user, chat_id, text)
            return True
        if action == "login_step_email":
            self.handle_login_email(user, chat_id, text)
            return True
        if action == "login_step_waiting_confirmation":
            self.handle_login_waiting_confirmation(user, chat_id, text)
            return True

        return False
