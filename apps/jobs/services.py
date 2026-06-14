"""Servicos de curadoria e formatacao para review de vagas."""

import time
from typing import Any

import structlog
from django.conf import settings
from django.db.models import Q

from apps.bot.messages import BOT_MESSAGES
from apps.core.portal_links import build_portal_url
from apps.jobs.models import Job, JobSearchLog, JobStatus
from apps.users.models import UserProfile
from infra.waha.protocols import JobSearcher, MessageSender

logger = structlog.get_logger(__name__)


def _serialize_local_job(job) -> dict[str, Any]:
    """Converte um `Job` no dict canônico usado pelas reviews do bot."""
    job_url = build_portal_url(settings.PORTAL_BASE_URL, f"/empresas/vagas/{job.pk}/")
    if job_url is None:
        logger.error(
            "invalid_portal_base_url_for_review",
            portal_base_url=settings.PORTAL_BASE_URL,
            job_id=job.pk,
        )

    return {
        "title": job.titulo,
        "company": job.company.nome,
        "location": job.company.endereco or "Curitiba, PR",
        "job_type": job.tipo,
        "job_url": job_url,
        "source": "local",
    }


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
    return [_serialize_local_job(job) for job in jobs]


def get_local_jobs_queryset_for_area(area):
    """QuerySet de `Job` aprovadas ofertadas para `area` (convenção "vazio = todas").

    Fonte única da regra de filtragem por área para os fluxos locais (resumo
    semanal e menu "Vagas do meu curso"). Reutiliza `Job.objects.for_area`
    (Fase 1) para não reimplementar a regra. Se `area` for `None` (curso do
    aluno sem área), retorna apenas as vagas ofertadas para todas as áreas.
    Retorna o queryset (sem corte) para que cada chamador defina seu próprio
    `limit` e escolha entre dicts serializados ou objetos `Job` completos.
    """
    return (
        Job.objects.for_area(area)
        .filter(status=JobStatus.APPROVED)
        .select_related("company")
        .order_by("-created_at")
    )


def get_local_jobs_for_area(area, limit: int = 5) -> list[dict[str, Any]]:
    """Vagas locais aprovadas ofertadas para `area`, serializadas para review."""
    jobs = get_local_jobs_queryset_for_area(area)[:limit]
    return [_serialize_local_job(job) for job in jobs]


def build_weekly_local_review(course, limit: int = 5) -> list[dict[str, Any]]:
    """Review semanal **só com vagas locais** da área do curso. NÃO chama jobspy.

    Usa `course.area` e a regra centralizada de áreas. Diferente de
    `build_review_for_user` (review sob demanda), aqui não há busca online —
    o envio semanal fica rápido e confiável (sem scraping ao vivo no loop).
    """
    area = getattr(course, "area", None)
    return get_local_jobs_for_area(area, limit=limit)


def search_with_config(
    course, job_searcher: JobSearcher, limit_per_term: int = 10
) -> list[dict[str, Any]]:
    """Search online jobs using each SearchTerm's own configuration.

    This is the SSoT (Single Source of Truth) for online job search.
    Each SearchTerm's to_search_kwargs() is used individually, so
    location, is_remote, job_type, country_indeed, etc. are respected
    per-term — matching the "Testar busca" admin behavior exactly.
    """
    search_terms = list(course.search_terms.filter(is_default=True).order_by("-priority"))
    if not search_terms:
        logger.warning(
            "no_search_terms_for_course",
            course_id=course.id,
            course_name=course.name,
        )
        return []

    results: list[dict[str, Any]] = []
    for term in search_terms:
        kwargs = term.to_search_kwargs(limit_override=limit_per_term)
        try:
            term_results = job_searcher.search(terms=[term.term], **kwargs)
            results.extend(term_results)
        except Exception:
            logger.warning(
                "search_with_config_term_failed",
                term=term.term,
                course_id=course.id,
                exc_info=True,
            )
    return results


def get_online_jobs_for_course(course, job_searcher: JobSearcher) -> list[dict[str, Any]]:
    """Search online jobs via JobSpy using default course terms.

    Delegates to search_with_config for SSoT search behavior.
    """
    return search_with_config(course, job_searcher, limit_per_term=10)


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


def build_review_for_user(course, job_searcher: JobSearcher) -> list[dict[str, Any]]:
    """Combine local and online jobs, deduplicate, and return top entries."""
    local_jobs = get_local_jobs_for_course(course)
    online_jobs = get_online_jobs_for_course(course, job_searcher)
    combined = deduplicate_jobs(local_jobs + online_jobs)
    return combined[:5]


def fetch_and_save_daily_jobs(job_searcher) -> dict[str, int]:
    """Scrapa todos os SearchTerms ativos e persiste em DailyJob (BOT-02).

    Chamada pela task fetch_daily_jobs — não chamar diretamente no webhook.
    Retorna estatísticas de execução para logging e monitoramento.
    """
    from datetime import date, timedelta

    from apps.courses.models import SearchTerm
    from apps.jobs.models import DailyJob, JobSearchLog

    today = date.today()
    search_terms = list(SearchTerm.objects.filter(is_default=True).select_related("course"))
    stats: dict[str, int] = {
        "terms_processed": 0,
        "jobs_saved": 0,
        "jobs_skipped": 0,
        "errors": 0,
    }

    for term in search_terms:
        kwargs = term.to_search_kwargs()
        try:
            results = job_searcher.search(terms=[term.term], **kwargs)
            to_create = [
                DailyJob(
                    search_term=term,
                    fetched_date=today,
                    title=r.get("title", ""),
                    company=r.get("company", ""),
                    location=r.get("location", ""),
                    job_url=r.get("job_url") or r.get("job_url_direct", ""),
                    description=r.get("description", ""),
                    job_type=r.get("job_type", ""),
                )
                for r in results
                if r.get("job_url") or r.get("job_url_direct")
            ]
            created = DailyJob.objects.bulk_create(to_create, ignore_conflicts=True)
            stats["jobs_saved"] += len(created)
            stats["jobs_skipped"] += len(to_create) - len(created)
            JobSearchLog.objects.create(
                user=None,
                search_term=term.term,
                location=term.location,
                job_type=term.job_type,
                results_count=len(results),
                filters=term.to_search_kwargs(),
                results_preview=results[:5],
            )
        except Exception:
            stats["errors"] += 1
            logger.warning(
                "fetch_daily_jobs_term_failed",
                term=term.term,
                exc_info=True,
            )
        stats["terms_processed"] += 1

    # Limpeza de vagas com mais de 7 dias (TTL configurado)
    deleted, _ = DailyJob.objects.filter(fetched_date__lt=today - timedelta(days=7)).delete()
    logger.info(
        "fetch_daily_jobs_completed",
        deleted_old=deleted,
        **stats,
    )
    return stats


def _format_job_lines(jobs: list[dict[str, Any]]) -> list[str]:
    """Linhas formatadas (uma vaga por bloco) compartilhadas pelas reviews."""
    lines: list[str] = []
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

    return lines


def format_review_message(course_name: str, jobs: list[dict[str, Any]]) -> str:
    """Format an on-demand review message (local + online) for WhatsApp."""
    lines = [
        BOT_MESSAGES.review.weekly_header.text.format(course_name=course_name),
        "",
        BOT_MESSAGES.review.weekly_summary.text.format(count=len(jobs)),
        "",
    ]
    lines.extend(_format_job_lines(jobs))
    lines.append(BOT_MESSAGES.review.weekly_footer.text)
    return "\n".join(lines)


def format_weekly_local_review_message(course_name: str, jobs: list[dict[str, Any]]) -> str:
    """Format the weekly **local-only** review message for WhatsApp delivery."""
    lines = [
        BOT_MESSAGES.review.weekly_local_header.text.format(course_name=course_name),
        "",
        BOT_MESSAGES.review.weekly_local_summary.text.format(count=len(jobs)),
        "",
    ]
    lines.extend(_format_job_lines(jobs))
    lines.append(BOT_MESSAGES.review.weekly_footer.text)
    return "\n".join(lines)


def send_weekly_reviews(
    *,
    message_sender: MessageSender,
    interval_seconds: float = 1.0,
) -> dict[str, int]:
    """Envia o resumo semanal **só de vagas locais** para usuários elegíveis.

    Diferente do review sob demanda, o caminho semanal:
    - usa apenas vagas locais da área do curso (`build_weekly_local_review`),
      **sem chamar jobspy** — envio rápido e confiável;
    - **sempre envia algo**: se não há vaga local nova, manda um aviso amigável
      (não fica em silêncio como antes).

    Stats: `sent` (lista de vagas enviada), `empty_notice` (aviso de vazio
    enviado) e `errors`.
    """
    users = (
        UserProfile.objects.filter(
            conversation_state__selected_course__isnull=False,
            phone_number__isnull=False,
        )
        .exclude(phone_number="")
        .select_related("conversation_state__selected_course__area")
    )

    stats: dict[str, int] = {"sent": 0, "empty_notice": 0, "errors": 0}
    logger.info("weekly_review_started", total_users=users.count())

    for user in users:
        selected_course = user.conversation_state.selected_course
        area = getattr(selected_course, "area", None)
        try:
            jobs = build_weekly_local_review(selected_course)
            if not jobs:
                msg = BOT_MESSAGES.review.weekly_no_local_jobs.text.format(
                    course_name=selected_course.name
                )
                message_sender.send_message(user.phone_number, msg)
                stats["empty_notice"] += 1
                logger.info(
                    "weekly_review_empty_notice",
                    user_id=user.id,
                    area=area.name if area else None,
                )
            else:
                msg = format_weekly_local_review_message(selected_course.name, jobs)
                message_sender.send_message(user.phone_number, msg)
                JobSearchLog.objects.create(
                    user=None,
                    search_term=selected_course.name,
                    location=None,
                    job_type=None,
                    results_count=len(jobs),
                    filters={},
                    results_preview=jobs[:5],
                )
                stats["sent"] += 1
                logger.info(
                    "weekly_review_sent",
                    user_id=user.id,
                    area=area.name if area else None,
                    jobs_count=len(jobs),
                )

            if interval_seconds > 0:
                time.sleep(interval_seconds)
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
