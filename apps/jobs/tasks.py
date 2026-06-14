"""Tasks Celery para curadoria e envio de review de vagas."""

from celery import shared_task

from .services import send_weekly_reviews


@shared_task(bind=True, max_retries=0)
def send_weekly_job_review(self) -> dict[str, int]:
    """Task thin que delega o fluxo semanal para a camada de servico.

    O caminho semanal é local-only (sem jobspy), então não construímos
    JobSearchService aqui.
    """
    from apps.bot.models import BotConfiguration
    from infra.waha.client import WahaClient

    waha_settings = BotConfiguration.get_active()
    waha_client = WahaClient(settings=waha_settings)

    return send_weekly_reviews(
        message_sender=waha_client,
        interval_seconds=1,
    )


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
