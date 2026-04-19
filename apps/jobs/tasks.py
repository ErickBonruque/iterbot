"""Tasks Celery para curadoria e envio de review de vagas."""

import time

import structlog
from celery import shared_task

from apps.users.models import UserProfile
from infra.jobspy.service import JobSearchService

from .services import build_review_for_user, format_review_message

logger = structlog.get_logger(__name__)


# Compatibilidade temporaria para chamadas legadas durante a migracao.
def _build_review_for_user(course, job_service: JobSearchService):
    return build_review_for_user(course, job_service)


# Compatibilidade temporaria para chamadas legadas durante a migracao.
def _format_review_message(course_name: str, jobs):
    return format_review_message(course_name, jobs)


@shared_task(bind=True, max_retries=0)
def send_weekly_job_review(self) -> dict[str, int]:
    """Send weekly job review to each authenticated student with a selected course.

    Args:
        None

    Returns:
        Dict with sent, no_jobs, and errors counts.

    Raises:
        Exception: Caught and logged per-user; never re-raised.
    """
    from apps.bot.models import BotConfiguration
    from infra.waha.client import WahaClient

    waha_settings = BotConfiguration.get_active()
    waha_client = WahaClient(settings=waha_settings)
    job_service = JobSearchService()

    users = (
        UserProfile.objects.filter(
            conversation_state__selected_course__isnull=False,
            phone_number__isnull=False,
        )
        .exclude(phone_number="")
        .select_related("conversation_state__selected_course")
    )

    stats: dict[str, int] = {"sent": 0, "no_jobs": 0, "errors": 0}

    logger.info("weekly_review_started", total_users=users.count())

    for user in users:
        selected_course = user.conversation_state.selected_course
        try:
            jobs = build_review_for_user(selected_course, job_service)

            if not jobs:
                stats["no_jobs"] += 1
                logger.debug(
                    "review_no_jobs",
                    user_id=user.id,
                    course=selected_course.name,
                )
                continue

            msg = format_review_message(selected_course.name, jobs)
            waha_client.send_message(user.phone_number, msg)
            stats["sent"] += 1

            logger.info(
                "review_sent",
                user_id=user.id,
                course=selected_course.name,
                jobs_count=len(jobs),
            )

            time.sleep(1)

        except Exception as exc:
            stats["errors"] += 1
            logger.error(
                "review_send_failed",
                user_id=user.id,
                course=selected_course.name if selected_course else None,
                error=str(exc),
                exc_info=True,
            )

    logger.info("weekly_review_completed", **stats)
    return stats
