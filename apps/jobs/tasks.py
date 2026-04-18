"""Tasks Celery para curadoria e envio de review de vagas."""

import time
from typing import Any

import structlog
from celery import shared_task
from django.conf import settings
from django.db.models import Q

from apps.bot.messages import BOT_MESSAGES
from apps.core.portal_links import build_portal_url
from apps.jobs.models import Job, JobStatus
from apps.users.models import UserProfile
from infra.jobspy.service import JobSearchService

logger = structlog.get_logger(__name__)


def _get_local_jobs_for_course(course) -> list[dict[str, Any]]:
    """Return approved local jobs relevant to the given course.

    Args:
        course: Course model instance with search_terms.

    Returns:
        List of dicts with title, company, location, job_type, job_url, source.
    """
    terms = list(
        course.search_terms.filter(is_default=True)
        .order_by("-priority")
        .values_list("term", flat=True)
    )
    if not terms:
        logger.warning(
            "no_search_terms_for_course_local_jobs",
            course_id=course.id,
            course_name=course.name,
        )
        return []

    term_query = Q()
    for term in terms:
        term_query |= Q(titulo__icontains=term) | Q(descricao__icontains=term)

    jobs = (
        Job.objects.filter(status=JobStatus.APPROVED)
        .filter(term_query)
        .select_related("company")
        .order_by("-created_at")[:10]
    )
    local_jobs: list[dict[str, Any]] = []
    for job in jobs:
        job_url = build_portal_url(settings.PORTAL_BASE_URL, f"/empresas/vagas/{job.pk}/")
        if job_url is None:
            logger.error(
                "invalid_portal_base_url_for_review",
                portal_base_url=settings.PORTAL_BASE_URL,
                job_id=job.pk,
            )

        local_jobs.append(
            {
                "title": job.titulo,
                "company": job.company.nome,
                "location": job.company.endereco or "Curitiba, PR",
                "job_type": job.tipo,
                "job_url": job_url,
                "source": "local",
            }
        )

    return local_jobs


def _get_online_jobs_for_course(course, job_service: JobSearchService) -> list[dict[str, Any]]:
    """Search online jobs via JobSpy using the course's default search terms.

    Args:
        course: Course model instance with search_terms.
        job_service: JobSearchService instance for making API calls.

    Returns:
        List of dicts with job data from LinkedIn/Indeed/Glassdoor.
    """
    terms = list(
        course.search_terms.filter(is_default=True)
        .order_by("-priority")
        .values_list("term", flat=True)
    )
    if not terms:
        logger.warning(
            "no_search_terms_for_course",
            course_id=course.id,
            course_name=course.name,
        )
        return []
    return job_service.search(terms, limit=10)


def _deduplicate(jobs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Remove duplicate jobs by (normalized title, normalized company).

    Args:
        jobs: List of job dictionaries.

    Returns:
        Deduplicated list of job dictionaries.
    """
    seen: set[tuple[str, str]] = set()
    unique: list[dict[str, Any]] = []
    for job in jobs:
        title = (job.get("title") or job.get("titulo") or "").lower().strip()
        company = (job.get("company") or "").lower().strip()
        key = (title, company)
        if key not in seen:
            seen.add(key)
            unique.append(job)
    return unique


def _build_review_for_user(course, job_service: JobSearchService) -> list[dict[str, Any]]:
    """Combine local and online jobs, deduplicate, and return up to 5.

    Args:
        course: Course model instance.
        job_service: JobSearchService instance.

    Returns:
        List of up to 5 unique job dictionaries.
    """
    local_jobs = _get_local_jobs_for_course(course)
    online_jobs = _get_online_jobs_for_course(course, job_service)
    combined = _deduplicate(local_jobs + online_jobs)
    return combined[:5]


def _format_review_message(course_name: str, jobs: list[dict[str, Any]]) -> str:
    """Format a job review message for WhatsApp delivery.

    Args:
        course_name: Name of the course for the header.
        jobs: List of job dictionaries to format.

    Returns:
        Formatted WhatsApp message string.
    """
    lines = [
        BOT_MESSAGES.review.weekly_header.text.format(course_name=course_name),
        "",
        BOT_MESSAGES.review.weekly_summary.text.format(count=len(jobs)),
        "",
    ]
    for i, job in enumerate(jobs, 1):
        title = job.get("title") or job.get("titulo") or "Vaga"
        company = job.get("company") or "Empresa"
        location = job.get("location") or "Curitiba, PR"
        job_type = job.get("job_type") or job.get("tipo") or ""
        url = job.get("job_url") or ""

        lines.append(f"*{i}. {title}* — {company}")

        loc_parts = [f"📍 {location}"]
        if job_type:
            loc_parts.append(f"💼 {job_type}")
        lines.append(" | ".join(loc_parts))

        if url:
            lines.append(f"🔗 {url}")
        lines.append("")

    lines.append(BOT_MESSAGES.review.weekly_footer.text)
    return "\n".join(lines)


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
            jobs = _build_review_for_user(selected_course, job_service)

            if not jobs:
                stats["no_jobs"] += 1
                logger.debug(
                    "review_no_jobs",
                    user_id=user.id,
                    course=selected_course.name,
                )
                continue

            msg = _format_review_message(selected_course.name, jobs)
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
