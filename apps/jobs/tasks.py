"""Tasks Celery para curadoria e envio de review de vagas."""

from celery import shared_task

from .services import send_weekly_reviews


@shared_task(bind=True, max_retries=0)
def send_weekly_job_review(self) -> dict[str, int]:
    """Task thin que delega o fluxo semanal para a camada de servico."""
    from apps.bot.models import BotConfiguration
    from infra.jobspy.service import JobSearchService
    from infra.waha.client import WahaClient

    waha_settings = BotConfiguration.get_active()
    waha_client = WahaClient(settings=waha_settings)
    job_searcher = JobSearchService()

    return send_weekly_reviews(
        message_sender=waha_client,
        job_searcher=job_searcher,
        interval_seconds=1,
    )
