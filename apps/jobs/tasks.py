"""Tasks Celery para curadoria e envio de review de vagas."""

from celery import shared_task
from django.conf import settings

from .services import send_weekly_reviews


@shared_task(bind=True, max_retries=0)
def send_weekly_job_review(self) -> dict[str, int]:
    """Envia um lote do resumo semanal e agenda o próximo se ainda houver público.

    O beat dispara toda segunda 08:00; cada execução manda no máximo
    `WEEKLY_REVIEW_MAX_PER_RUN` mensagens e, se sobrar gente, reagenda a si mesma
    após `WEEKLY_REVIEW_BATCH_PAUSE_SECONDS`. Um lote sem nenhum envio bem-sucedido
    (ex.: WAHA fora do ar) não reagenda — evita laço; a próxima segunda tenta de novo.
    O caminho semanal é local-only (sem jobspy).
    """
    from apps.bot.models import BotConfiguration
    from infra.waha.client import WahaClient

    waha_client = WahaClient(settings=BotConfiguration.get_active())

    stats = send_weekly_reviews(
        message_sender=waha_client,
        min_interval_seconds=settings.WEEKLY_REVIEW_MIN_INTERVAL_SECONDS,
        max_interval_seconds=settings.WEEKLY_REVIEW_MAX_INTERVAL_SECONDS,
        max_per_run=settings.WEEKLY_REVIEW_MAX_PER_RUN,
    )

    progressed = stats["sent"] + stats["empty_notice"] > 0
    if stats["remaining"] > 0 and progressed:
        send_weekly_job_review.apply_async(countdown=settings.WEEKLY_REVIEW_BATCH_PAUSE_SECONDS)
    return stats


@shared_task(bind=True, max_retries=3, default_retry_delay=300)
def fetch_daily_jobs(self) -> dict[str, int]:
    """Task thin: scrapa vagas por SearchTerm e persiste em DailyJob (BOT-02).

    Roda diariamente às 07:00 Brasília via Celery Beat.
    Não chamar diretamente no handler de webhook — causa timeout.
    """
    from apps.jobs.services import fetch_and_save_daily_jobs
    from infra.jobspy.service import JobSearchService

    searcher = JobSearchService()
    return fetch_and_save_daily_jobs(job_searcher=searcher)
