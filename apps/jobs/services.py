"""Servicos de curadoria e formatacao para review de vagas."""

from typing import Any

import structlog
from django.conf import settings
from django.db.models import Q

from apps.bot.messages import BOT_MESSAGES
from apps.core.portal_links import build_portal_url
from apps.jobs.models import Job, JobStatus
from infra.jobspy.service import JobSearchService

logger = structlog.get_logger(__name__)


def get_local_jobs_for_course(course) -> list[dict[str, Any]]:
    """Return approved local jobs relevant to the given course."""
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


def get_online_jobs_for_course(course, job_service: JobSearchService) -> list[dict[str, Any]]:
    """Search online jobs via JobSpy using default course terms."""
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


def deduplicate_jobs(jobs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Remove duplicate jobs by normalized title and company."""
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


def build_review_for_user(course, job_service: JobSearchService) -> list[dict[str, Any]]:
    """Combine local and online jobs, deduplicate, and return top entries."""
    local_jobs = get_local_jobs_for_course(course)
    online_jobs = get_online_jobs_for_course(course, job_service)
    combined = deduplicate_jobs(local_jobs + online_jobs)
    return combined[:5]


def format_review_message(course_name: str, jobs: list[dict[str, Any]]) -> str:
    """Format a weekly review message for WhatsApp delivery."""
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
