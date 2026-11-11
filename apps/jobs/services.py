"""Serviços de vagas: coleta diária filtrada, reviews e resumo semanal."""

import random
import time
from collections.abc import Callable
from datetime import timedelta
from typing import Any

import structlog
from django.conf import settings
from django.db.models import Max, Q
from django.urls import reverse
from django.utils import timezone

from apps.bot.messages import BOT_MESSAGES
from apps.core.portal_links import build_portal_url
from apps.jobs.models import Job, JobSearchLog
from apps.jobs.relevance import classify, dedupe, parse_terms
from apps.users.models import UserProfile
from infra.waha.protocols import JobSearcher, MessageSender

logger = structlog.get_logger(__name__)


def _serialize_local_job(job) -> dict[str, Any]:
    """Converte um `Job` no dict canônico usado pelas reviews do bot."""
    job_url = build_portal_url(
        settings.PORTAL_BASE_URL, reverse("jobs:public_detail", kwargs={"pk": job.pk})
    )
    if job_url is None:
        logger.error(
            "invalid_portal_base_url_for_review",
            portal_base_url=settings.PORTAL_BASE_URL,
            job_id=job.pk,
        )

    return {
        "title": job.titulo,
        "company": job.company.nome,
        "location": job.company.endereco or "",
        "job_type": job.tipo,
        "job_url": job_url,
        "source": "local",
    }


def get_local_jobs_queryset_for_area(area):
    """QuerySet de `Job` aprovadas ofertadas para `area` (convenção "vazio = todas").

    Fonte única da regra de filtragem por área para os fluxos locais (resumo
    semanal e menu "Vagas do meu curso"). Reutiliza `Job.objects.for_area`
    (Fase 1) para não reimplementar a regra. Se `area` for `None` (curso do
    aluno sem área), retorna apenas as vagas ofertadas para todas as áreas.
    Retorna o queryset (sem corte) para que cada chamador defina seu próprio
    `limit` e escolha entre dicts serializados ou objetos `Job` completos.
    """
    return Job.objects.for_area(area).publicadas().select_related("company").order_by("-created_at")


def get_local_jobs_for_area(area, limit: int = 5) -> list[dict[str, Any]]:
    """Vagas locais aprovadas ofertadas para `area`, serializadas para review."""
    jobs = get_local_jobs_queryset_for_area(area)[:limit]
    return [_serialize_local_job(job) for job in jobs]


def build_weekly_local_review(course, limit: int = 5) -> list[dict[str, Any]]:
    """Review semanal **só com vagas locais** da área do curso. NÃO chama jobspy.

    Usa `course.area` e a regra centralizada de áreas. Diferente de
    `build_review_for_user` (review sob demanda), aqui não entram as vagas
    online (jobspy) — o resumo semanal divulga as empresas parceiras.
    """
    area = getattr(course, "area", None)
    return get_local_jobs_for_area(area, limit=limit)


# Uma empresa não pode ocupar a lista inteira (a BairesDev publica a mesma vaga
# em 20 cidades, com títulos levemente diferentes).
MAX_JOBS_PER_COMPANY = 2


def get_latest_daily_jobs(course):
    """Vagas online pré-buscadas da última coleta do curso, por termo.

    Usa a data mais recente com vaga (não "hoje"): antes das 07:00, ou se o
    scraper falhar num dia, o aluno ainda vê a coleta anterior.

    Returns:
        QuerySet de DailyJob dos termos ativos do curso, ordenado pela
        prioridade do termo — vazio se o curso nunca teve vaga coletada.
    """
    from apps.jobs.models import DailyJob

    jobs = DailyJob.objects.filter(search_term__course=course, search_term__is_default=True)
    latest = jobs.aggregate(latest=Max("fetched_date"))["latest"]
    if latest is None:
        return DailyJob.objects.none()
    return jobs.filter(fetched_date=latest).order_by("-search_term__priority", "id")


def build_review_for_user(course, limit: int = 5) -> list[dict[str, Any]]:
    """Review sob demanda: vagas de empresas parceiras + vagas online do curso.

    Lê as vagas que `fetch_daily_jobs` já coletou e filtrou — antes rodava o
    jobspy ao vivo para todos os termos do curso, com o aluno esperando.
    """
    local_jobs = get_local_jobs_for_area(getattr(course, "area", None), limit=limit)
    online_jobs = list(
        get_latest_daily_jobs(course).values("title", "company", "location", "job_url")
    )
    return dedupe(local_jobs + online_jobs)[:limit]


def select_relevant_jobs(term, records: list[dict[str, Any]]):
    """Aplica o filtro de relevância do termo às vagas que a busca trouxe.

    Returns:
        (vagas mantidas, Counter com o motivo de cada decisão). Termo sem
        `scope` mantém tudo (comportamento antigo, para termos do admin).
    """
    from collections import Counter

    if not term.scope:
        return records, Counter()

    course = term.course
    title_keywords = parse_terms(course.job_title_keywords)
    course_names = parse_terms(course.job_course_names)
    reasons: Counter = Counter()
    kept = []
    for record in records:
        # O Indeed aplica "apenas remotas"; o LinkedIn ignora o filtro.
        board_remote = term.is_remote and record.get("site") == "indeed"
        verdict = classify(
            record,
            title_keywords=title_keywords,
            course_names=course_names,
            scope=term.scope,
            board_remote=board_remote,
        )
        reasons[verdict] += 1
        if verdict == "ok":
            kept.append(record)
    return dedupe(kept, max_per_company=MAX_JOBS_PER_COMPANY), reasons


def _job_field(value: Any, max_length: int | None = None) -> str:
    """Normaliza um campo textual vindo do scraper para persistência.

    O jobspy entrega `None` nas colunas que não preencheu (NaN convertido) —
    `record.get("campo", "")` não protege disso, porque a chave existe com valor
    nulo. Como os campos de DailyJob são NOT NULL, um único registro assim
    derrubava o bulk_create do termo inteiro (`description` vem sempre nula
    quando `linkedin_fetch_description` está desligado). Truncar no limite da
    coluna evita perder o lote pelo mesmo motivo.
    """
    text = str(value).strip() if value is not None else ""
    return text[:max_length] if max_length else text


def fetch_and_save_daily_jobs(job_searcher: JobSearcher) -> dict[str, int]:
    """Scrapa todos os SearchTerms ativos, filtra e persiste em DailyJob (BOT-02).

    Chamada pela task fetch_daily_jobs — não chamar diretamente no webhook.

    - Buscas idênticas (mesmo termo e parâmetros) rodam uma vez só: a busca
      regional e a remota amplas se repetem nos três cursos, e cada scrape a
      mais é uma requisição a mais para o LinkedIn bloquear.
    - Cada termo passa pelo filtro de relevância do seu curso
      (`select_relevant_jobs`) antes de salvar.

    Stats: `jobs_found` (o que os sites devolveram), `jobs_filtered`
    (recusadas pelo filtro), `jobs_saved`/`jobs_skipped` (novas/repetidas),
    `terms_empty` (sites devolveram zero), `errors`.
    """
    import json
    from collections import Counter
    from datetime import date, timedelta

    from apps.courses.models import SearchTerm
    from apps.jobs.models import DailyJob, JobSearchLog

    today = date.today()
    search_terms = list(SearchTerm.objects.filter(is_default=True).select_related("course"))
    stats: dict[str, int] = {
        "terms_processed": 0,
        "terms_empty": 0,
        "jobs_found": 0,
        "jobs_filtered": 0,
        "jobs_saved": 0,
        "jobs_skipped": 0,
        "errors": 0,
    }
    scrape_cache: dict[str, list[dict[str, Any]]] = {}

    for term in search_terms:
        kwargs = term.to_search_kwargs()
        cache_key = json.dumps([term.term, kwargs], sort_keys=True, default=str)
        try:
            if cache_key not in scrape_cache:
                scrape_cache[cache_key] = job_searcher.search(terms=[term.term], **kwargs)
            results = scrape_cache[cache_key]
            if not results:
                # `search()` engole falhas de scrape e devolve lista vazia, então
                # esta contagem é o que separa "dia sem vagas" de "scraper quebrado".
                stats["terms_empty"] += 1
            relevant, reasons = select_relevant_jobs(term, results)
            stats["jobs_found"] += len(results)
            stats["jobs_filtered"] += len(results) - len(relevant)
            to_create = [
                DailyJob(
                    search_term=term,
                    fetched_date=today,
                    title=_job_field(r.get("title"), 255),
                    company=_job_field(r.get("company"), 255),
                    location=_job_field(r.get("location"), 255),
                    job_url=_job_field(r.get("job_url") or r.get("job_url_direct"), 1000),
                    description=_job_field(r.get("description")),
                    job_type=_job_field(r.get("job_type"), 50),
                    source=_job_field(r.get("site"), 20),
                )
                for r in relevant
                if r.get("job_url") or r.get("job_url_direct")
            ]
            # `bulk_create(ignore_conflicts=True)` devolve a lista que recebeu —
            # o Postgres não retorna as linhas inseridas nesse modo, então contar
            # o retorno marcaria toda vaga repetida como nova. Medimos pela
            # diferença de linhas do termo no dia.
            saved_before = DailyJob.objects.filter(search_term=term, fetched_date=today).count()
            DailyJob.objects.bulk_create(to_create, ignore_conflicts=True)
            saved = (
                DailyJob.objects.filter(search_term=term, fetched_date=today).count() - saved_before
            )
            stats["jobs_saved"] += saved
            stats["jobs_skipped"] += len(to_create) - saved
            logger.info(
                "fetch_daily_jobs_term",
                term=term.term,
                course=term.course.name,
                scope=term.scope or None,
                found=len(results),
                kept=len(relevant),
                reasons=dict(reasons),
                # Quanto cada fonte contribui — base para decidir quais manter.
                found_by_site=dict(Counter(r.get("site") or "?" for r in results)),
                kept_by_site=dict(Counter(r.get("site") or "?" for r in relevant)),
            )
            JobSearchLog.objects.create(
                user=None,
                search_term=term.term,
                location=term.location,
                job_type=term.job_type,
                results_count=len(relevant),
                filters=kwargs,
                results_preview=relevant[:5],
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
        scrapes=len(scrape_cache),
        **stats,
    )
    if search_terms and not stats["jobs_found"]:
        # Nenhum site devolveu vaga alguma: é falha sistêmica (scraper bloqueado,
        # rede, runner quebrado), não um dia fraco nem o filtro. Evento próprio
        # para alarme.
        logger.error("fetch_daily_jobs_no_results", **stats)
    return stats


def _format_job_lines(jobs: list[dict[str, Any]]) -> list[str]:
    """Linhas formatadas (uma vaga por bloco) compartilhadas pelas reviews."""
    lines: list[str] = []
    for i, job in enumerate(jobs, 1):
        title = job.get("title") or job.get("titulo") or "Vaga"
        company = job.get("company") or "Empresa"
        location = job.get("location") or ""
        job_type = job.get("job_type") or job.get("tipo") or ""
        url = job.get("job_url") or ""

        lines.append(f"*{i}. {title}* — {company}")

        loc_parts = [f"📍 {location}"] if location else []
        if job_type:
            loc_parts.append(f"💼 {job_type}")
        if loc_parts:
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


# Quem recebeu há menos que isto já foi atendido neste ciclo semanal (o beat
# dispara toda segunda; os lotes seguintes do mesmo dia não repetem ninguém).
WEEKLY_REVIEW_CYCLE = timedelta(days=6)


def weekly_review_audience():
    """Alunos que devem receber o resumo semanal neste ciclo.

    Só quem aceitou o texto de privacidade, não pediu "parar", tem curso
    escolhido e ainda não recebeu nos últimos `WEEKLY_REVIEW_CYCLE`.
    """
    cutoff = timezone.now() - WEEKLY_REVIEW_CYCLE
    return (
        UserProfile.objects.filter(
            conversation_state__selected_course__isnull=False,
            phone_number__isnull=False,
            privacy_consent_at__isnull=False,
            weekly_review_opt_out=False,
        )
        .filter(Q(weekly_review_sent_at__isnull=True) | Q(weekly_review_sent_at__lt=cutoff))
        .exclude(phone_number="")
        .select_related("conversation_state__selected_course__area")
        .order_by("id")
    )


def send_weekly_reviews(
    *,
    message_sender: MessageSender,
    min_interval_seconds: float,
    max_interval_seconds: float,
    max_per_run: int,
    sleep: Callable[[float], Any] = time.sleep,
) -> dict[str, int]:
    """Envia um lote do resumo semanal **só de vagas locais**.

    - usa apenas vagas locais da área do curso (`build_weekly_local_review`),
      **sem chamar jobspy**;
    - **sempre envia algo**: sem vaga local nova, manda um aviso amigável;
    - ritmo anti-bloqueio do WhatsApp: no máximo `max_per_run` mensagens, com
      pausa aleatória entre `min_interval_seconds` e `max_interval_seconds`
      entre elas (nunca depois da última). Quem fica de fora sai nos lotes
      seguintes (a task reagenda) — `weekly_review_sent_at` impede repetição;
    - envio recusado pelo WAHA (`send_message` → False) conta como erro e o
      aluno continua pendente.

    Stats: `sent`, `empty_notice`, `errors` e `remaining` (pendentes após o lote).
    """
    batch = list(weekly_review_audience()[:max_per_run])
    stats: dict[str, int] = {"sent": 0, "empty_notice": 0, "errors": 0, "remaining": 0}
    logger.info("weekly_review_started", batch_size=len(batch), max_per_run=max_per_run)

    for index, user in enumerate(batch):
        if index > 0:
            sleep(random.uniform(min_interval_seconds, max_interval_seconds))

        selected_course = user.conversation_state.selected_course
        area = getattr(selected_course, "area", None)
        try:
            jobs = build_weekly_local_review(selected_course)
            if jobs:
                msg = format_weekly_local_review_message(selected_course.name, jobs)
            else:
                msg = BOT_MESSAGES.review.weekly_no_local_jobs.text.format(
                    course_name=selected_course.name
                )

            if not message_sender.send_message(user.phone_number, msg):
                stats["errors"] += 1
                logger.error("weekly_review_send_refused", user_id=user.id)
                continue

            user.weekly_review_sent_at = timezone.now()
            user.save(update_fields=["weekly_review_sent_at", "updated_at"])

            if jobs:
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
            else:
                stats["empty_notice"] += 1
                logger.info(
                    "weekly_review_empty_notice",
                    user_id=user.id,
                    area=area.name if area else None,
                )
        except Exception as exc:
            stats["errors"] += 1
            logger.error(
                "review_send_failed",
                user_id=user.id,
                course=selected_course.name if selected_course else None,
                error=str(exc),
                exc_info=True,
            )

    stats["remaining"] = weekly_review_audience().count()
    logger.info("weekly_review_completed", **stats)
    return stats
