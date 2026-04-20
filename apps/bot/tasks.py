"""Tasks Celery para monitoramento e estabilidade do bot WhatsApp."""

import structlog
from celery import shared_task

from infra.waha.protocols import EmailConfirmationDispatcher

logger = structlog.get_logger(__name__)


class CeleryEmailConfirmationDispatcher:
    """Concrete dispatcher for confirmation emails using Celery."""

    def dispatch_confirmation_email(self, user_id: int) -> None:
        send_confirmation_email.delay(user_id)


@shared_task(bind=True, max_retries=0)
def check_waha_health(self) -> dict:
    """Check WAHA health and delegate reconnect policy to health monitor."""
    try:
        from apps.bot.health import BotHealthMonitor

        monitor = BotHealthMonitor()
        return monitor.check_and_reconnect()
    except Exception as exc:
        logger.error(
            "waha_health_check_task_failed",
            error=str(exc),
            exc_info=True,
        )
        return {"status": "error", "error": str(exc)}


@shared_task(bind=True, max_retries=0)
def clean_old_health_checks(self) -> dict:
    """Remove BotHealthCheck records older than 7 days."""
    try:
        from apps.bot.health import BotHealthMonitor

        monitor = BotHealthMonitor()
        deleted_count = monitor.clean_old_health_checks(days=7)
        logger.info(
            "health_checks_cleanup_completed",
            deleted_count=deleted_count,
        )
        return {"deleted_count": deleted_count}
    except Exception as exc:
        logger.error(
            "health_checks_cleanup_failed",
            error=str(exc),
            exc_info=True,
        )
        return {"error": str(exc)}


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_confirmation_email(self, user_id: int) -> dict:
    """Send email confirmation via dedicated email service."""
    from apps.bot.email_service import send_confirmation_email_to_user

    try:
        result = send_confirmation_email_to_user(user_id)
        if result["status"] == "sent":
            logger.info(
                "confirmation_email_sent",
                user_id=user_id,
                email=result.get("email"),
            )
        elif result["status"] == "skipped":
            logger.info("email_already_verified_skipping", user_id=user_id)
        else:
            logger.warning(
                "confirmation_email_service_rejected",
                user_id=user_id,
                reason=result.get("reason"),
            )
        return result
    except Exception as exc:
        logger.error(
            "confirmation_email_failed",
            user_id=user_id,
            error=str(exc),
            exc_info=True,
        )
        raise self.retry(exc=exc) from exc
