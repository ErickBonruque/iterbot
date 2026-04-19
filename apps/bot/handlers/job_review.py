"""Handler para consulta sob demanda de review de vagas (opcao 4 do menu)."""

import structlog

from apps.bot.messages import BOT_MESSAGES
from apps.bot.models import ConversationState
from apps.users.models import UserProfile
from infra.waha.protocols import JobSearcher, MessageSender

from .base import BaseHandler

logger = structlog.get_logger(__name__)


class JobReviewHandler(BaseHandler):
    """Sends on-demand job review to the student."""

    def __init__(self, waha_client: MessageSender, job_service: JobSearcher) -> None:
        super().__init__(waha_client)
        self.job_service = job_service

    def _get_conversation_state(self, user: UserProfile) -> ConversationState:
        conversation_state, _ = ConversationState.objects.get_or_create(user=user)
        return conversation_state

    def send_review(self, user: UserProfile, chat_id: str) -> None:
        from apps.jobs.tasks import _build_review_for_user, _format_review_message

        selected_course = self._get_conversation_state(user).selected_course
        if not selected_course:
            self.send_msg(
                user,
                chat_id,
                self.resolve_message(
                    BOT_MESSAGES.review.missing_course.key,
                    BOT_MESSAGES.review.missing_course.text,
                ),
            )
            logger.info("review_requested_no_course", user_id=user.id)
            return

        self.send_msg(
            user,
            chat_id,
            self.resolve_message(
                BOT_MESSAGES.review.searching_review.key,
                BOT_MESSAGES.review.searching_review.text,
            ),
        )

        try:
            jobs = _build_review_for_user(selected_course, self.job_service)
        except Exception as exc:
            logger.error(
                "review_on_demand_failed",
                user_id=user.id,
                course=selected_course.name,
                error=str(exc),
                exc_info=True,
            )
            self.send_msg(
                user,
                chat_id,
                self.resolve_message(
                    BOT_MESSAGES.review.review_error.key,
                    BOT_MESSAGES.review.review_error.text,
                ),
            )
            return

        if not jobs:
            self.send_msg(
                user,
                chat_id,
                self.resolve_message(
                    BOT_MESSAGES.review.no_jobs.key,
                    BOT_MESSAGES.review.no_jobs.text,
                ),
            )
            logger.info(
                "review_on_demand_no_jobs",
                user_id=user.id,
                course=selected_course.name,
            )
            return

        msg = _format_review_message(selected_course.name, jobs)
        self.send_msg(user, chat_id, msg)
        logger.info(
            "review_on_demand_sent",
            user_id=user.id,
            course=selected_course.name,
            jobs_count=len(jobs),
        )

    def handle(self, user: UserProfile, chat_id: str, text: str) -> bool:
        return False
