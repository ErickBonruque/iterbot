"""Signal handlers for Celery task lifecycle events."""

import structlog
from celery.signals import task_failure
from django.db.utils import OperationalError

logger = structlog.get_logger(__name__)


@task_failure.connect
def on_task_failure(sender=None, task_id=None, exception=None, **kwargs):
    """
    Registra falha de tarefa Celery em BotMetrics (METR-05, D-03).
    Disparado automaticamente pelo Celery quando qualquer tarefa falha.
    """
    try:
        from apps.bot.models import BotMetrics

        BotMetrics.objects.create(
            metric_name="celery.task_failure",
            value=1,
            metadata={
                "task_name": sender.name if sender else "unknown",
                "task_id": task_id,
                "error": str(exception)[:500],
                "exception_type": type(exception).__name__,
            },
        )
    except OperationalError:
        logger.error("failed_to_record_task_failure", task_id=task_id)
    except Exception as exc:
        logger.error("unexpected_error_in_task_failure_signal", error=str(exc))
