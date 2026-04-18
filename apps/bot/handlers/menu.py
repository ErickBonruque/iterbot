"""Menu handler for displaying navigation options."""
import structlog

from apps.bot.messages import BOT_MESSAGES
from apps.core.portal_links import build_portal_url
from apps.users.models import UserProfile

from .base import BaseHandler

logger = structlog.get_logger(__name__)


class MenuHandler(BaseHandler):
    """Handles menu display and navigation."""

    def send_menu(self, user: UserProfile, chat_id: str) -> None:
        if user.is_authenticated_utfpr:
            menu_text = self.resolve_message(
                BOT_MESSAGES.menu.main_authenticated.key,
                BOT_MESSAGES.menu.main_authenticated.text,
                brand_header=BOT_MESSAGES.menu.brand_header,
                ra=user.ra or "Não cadastrado",
            )
        else:
            menu_text = self.resolve_message(
                BOT_MESSAGES.menu.main_unauthenticated.key,
                BOT_MESSAGES.menu.main_unauthenticated.text,
                brand_header=BOT_MESSAGES.menu.brand_header,
            )

        self.send_msg(user, chat_id, menu_text)
        logger.info("menu_displayed", user_id=user.id, authenticated=user.is_authenticated_utfpr)

    def send_company_onboarding_menu(self, user: UserProfile, chat_id: str) -> None:
        menu_text = self.resolve_message(
            BOT_MESSAGES.menu.company_onboarding_menu.key,
            BOT_MESSAGES.menu.company_onboarding_menu.text,
            brand_header=BOT_MESSAGES.menu.brand_header,
        )
        self.send_msg(user, chat_id, menu_text)

    def send_company_onboarding_links(
        self,
        user: UserProfile,
        chat_id: str,
        option: str,
        portal_base_url: str,
    ) -> bool:
        if option == "1":
            signup_url = build_portal_url(portal_base_url, "/empresas/signup/")
            if signup_url is None:
                return False

            msg = self.resolve_message(
                BOT_MESSAGES.menu.company_onboarding_signup.key,
                BOT_MESSAGES.menu.company_onboarding_signup.text,
                signup_url=signup_url,
            )
            self.send_msg(user, chat_id, msg)
            return True

        if option == "2":
            login_url = build_portal_url(portal_base_url, "/empresas/login/")
            new_job_url = build_portal_url(portal_base_url, "/empresas/vagas/nova/")
            if login_url is None or new_job_url is None:
                return False

            msg = self.resolve_message(
                BOT_MESSAGES.menu.company_onboarding_publish.key,
                BOT_MESSAGES.menu.company_onboarding_publish.text,
                login_url=login_url,
                new_job_url=new_job_url,
            )
            self.send_msg(user, chat_id, msg)
            return True

        return False

    def send_unknown_command(self, user: UserProfile, chat_id: str) -> None:
        msg = self.resolve_message(
            BOT_MESSAGES.menu.unknown_command.key,
            BOT_MESSAGES.menu.unknown_command.text,
        )
        self.send_msg(user, chat_id, msg)
        logger.debug("unknown_command_sent", user_id=user.id)

    def handle(self, user: UserProfile, chat_id: str, text: str) -> bool:
        return False
