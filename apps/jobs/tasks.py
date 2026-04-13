"""Tasks Celery para curadoria e envio de review de vagas."""

import time
from typing import Any

import structlog
from celery import shared_task
from django.conf import settings
from django.db.models import Q

from apps.jobs.models import Job, JobStatus
from apps.users.models import UserProfile
from infra.jobspy.service import JobSearchService

logger = structlog.get_logger(__name__)


def _get_local_jobs_for_course(course) -> list[dict[str, Any]]:
    """Retorna vagas locais aprovadas e relevantes ao curso."""
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
    portal_base = getattr(settings, "PORTAL_BASE_URL", "http://localhost:8000")
    return [
        {
            "title": job.titulo,
            "company": job.company.nome,
            "location": job.company.endereco or "Curitiba, PR",
            "job_type": job.tipo,
            "job_url": f"{portal_base}/empresas/vagas/{job.pk}/",
            "source": "local",
        }
        for job in jobs
    ]


def _get_online_jobs_for_course(course, job_service: JobSearchService) -> list[dict[str, Any]]:
    """Busca vagas online via JobSpy usando termos padrao do curso."""
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
    """Deduplicacao por (titulo normalizado, empresa normalizada)."""
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
    """Combina vagas locais + online e retorna no maximo 5 apos deduplicacao."""
    local_jobs = _get_local_jobs_for_course(course)
    online_jobs = _get_online_jobs_for_course(course, job_service)
    combined = _deduplicate(local_jobs + online_jobs)
    return combined[:5]


def _format_review_message(course_name: str, jobs: list[dict[str, Any]]) -> str:
    """Formata mensagem de review para WhatsApp (D-06)."""
    lines = [
        f"🎓 *Review de Vagas — {course_name}*",
        "",
        f"Encontrei *{len(jobs)}* oportunidades para voce esta semana:",
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

    lines.append('_Para ver mais vagas, acesse o menu e escolha "Buscar Vagas"._')
    return "\n".join(lines)


@shared_task(bind=True, max_retries=0)
def send_weekly_job_review(self) -> dict[str, int]:
    """Envia review semanal para cada aluno com selected_course definido."""
    from apps.bot.models import BotConfiguration
    from infra.waha.client import WahaClient

    waha_settings = BotConfiguration.get_active()
    waha_client = WahaClient(settings=waha_settings)
    job_service = JobSearchService()

    users = (
        UserProfile.objects.filter(selected_course__isnull=False, phone_number__isnull=False)
        .exclude(phone_number="")
        .select_related("selected_course")
    )

    stats: dict[str, int] = {"sent": 0, "no_jobs": 0, "errors": 0}

    logger.info("weekly_review_started", total_users=users.count())

    for user in users:
        try:
            jobs = _build_review_for_user(user.selected_course, job_service)

            if not jobs:
                stats["no_jobs"] += 1
                logger.debug(
                    "review_no_jobs",
                    user_id=user.id,
                    course=user.selected_course.name,
                )
                continue

            msg = _format_review_message(user.selected_course.name, jobs)
            waha_client.send_message(user.phone_number, msg)
            stats["sent"] += 1

            logger.info(
                "review_sent",
                user_id=user.id,
                course=user.selected_course.name,
                jobs_count=len(jobs),
            )

            time.sleep(1)

        except Exception as exc:
            stats["errors"] += 1
            logger.error(
                "review_send_failed",
                user_id=user.id,
                course=user.selected_course.name if user.selected_course else None,
                error=str(exc),
                exc_info=True,
            )

    logger.info("weekly_review_completed", **stats)
    return stats
