"""Tasks Celery para monitoramento e estabilidade do bot WhatsApp."""

import structlog
from celery import shared_task

logger = structlog.get_logger(__name__)


class CeleryEmailConfirmationDispatcher:
    """Concrete dispatcher for confirmation emails using Celery."""

    def dispatch_confirmation_email(self, user_id: int) -> None:
        send_confirmation_email.delay(user_id)

    def dispatch_company_confirmation_email(self, user_id: int) -> None:
        send_company_confirmation_email.delay(user_id)


@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def process_webhook_message(self, chat_id: str, body: str) -> dict:
    """Processa mensagem recebida pelo webhook de forma assíncrona."""
    try:
        from apps.bot.services import BotService

        bot = BotService()
        bot.process_message(chat_id, body, False)
        logger.info("webhook_message_processed", chat_id=chat_id)
        return {"status": "processed", "chat_id": chat_id}
    except Exception as exc:
        logger.error(
            "webhook_message_processing_failed",
            chat_id=chat_id,
            error=str(exc),
            exc_info=True,
        )
        raise self.retry(exc=exc) from exc


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
def attempt_waha_reconnect(self, attempt: int = 1) -> dict:
    """Executa uma tentativa de reconexão WAHA agendada com countdown (sem sleep bloqueante)."""
    try:
        from apps.bot.health import BotHealthMonitor

        monitor = BotHealthMonitor()
        success = monitor.attempt_reconnect(attempt=attempt)
        return {"attempt": attempt, "success": success}
    except Exception as exc:
        logger.error(
            "attempt_waha_reconnect_task_failed",
            attempt=attempt,
            error=str(exc),
            exc_info=True,
        )
        return {"attempt": attempt, "success": False, "error": str(exc)}


@shared_task(bind=True, max_retries=0)
def clean_old_health_checks(self) -> dict:
    """Remove BotHealthCheck records older than 7 days."""
    try:
        from apps.bot.health import BotHealthMonitor

        monitor = BotHealthMonitor()
        deleted_count = monitor.clean_old_health_checks(days=90)
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
def send_company_confirmation_email(self, user_id: int) -> dict:
    """Send company WhatsApp-link confirmation email."""
    from apps.bot.email_service import send_company_confirmation_email_to_user

    try:
        result = send_company_confirmation_email_to_user(user_id)
        if result["status"] == "sent":
            logger.info("company_confirmation_email_sent", user_id=user_id)
        elif result["status"] == "skipped":
            logger.info("company_already_authenticated_skipping", user_id=user_id)
        else:
            logger.warning(
                "company_confirmation_email_service_rejected",
                user_id=user_id,
                reason=result.get("reason"),
            )
        return result
    except Exception as exc:
        logger.error(
            "company_confirmation_email_failed", user_id=user_id, error=str(exc), exc_info=True
        )
        raise self.retry(exc=exc) from exc


@shared_task(bind=True, max_retries=3, default_retry_delay=10)
def notify_company_confirmed_whatsapp(self, user_profile_id: int) -> dict:
    """Envia mensagem proativa no WhatsApp após confirmação do magic link empresa."""
    try:
        from apps.bot.models import BotConfiguration, ConversationState
        from apps.bot.state_machine import STATE_IDLE, apply_state_transition
        from apps.users.models import UserProfile
        from infra.waha.client import WahaClient

        profile = UserProfile.objects.select_related("company").get(pk=user_profile_id)
        if not profile.is_company_authenticated or profile.company is None:
            return {"status": "skipped", "reason": "not_authenticated"}

        waha_settings = BotConfiguration.get_active()
        client = WahaClient(settings=waha_settings)

        # Reseta estado para idle antes de enviar o menu.
        conv, _ = ConversationState.objects.get_or_create(user=profile)
        apply_state_transition(conversation_state=conv, next_state=STATE_IDLE, clear_flow_data=True)

        company_name = profile.company.nome
        client.send_message(
            profile.phone_number,
            f"✅ *Vínculo confirmado!*\n\n"
            f"Sua conta *{company_name}* está conectada ao IterBot.\n\n"
            f"Digite *menu* para acessar o painel da empresa.",
        )
        logger.info("company_confirmed_whatsapp_sent", user_id=user_profile_id)
        return {"status": "sent", "user_id": user_profile_id}
    except Exception as exc:
        logger.error(
            "company_confirmed_whatsapp_failed",
            user_id=user_profile_id,
            error=str(exc),
            exc_info=True,
        )
        raise self.retry(exc=exc) from exc


@shared_task(bind=True, max_retries=3, default_retry_delay=10)
def notify_student_confirmed_whatsapp(self, user_profile_id: int) -> dict:
    """Envia mensagem proativa no WhatsApp após confirmação de e-mail do aluno.

    Reseta o ConversationState preso em login_step_waiting_confirmation e
    notifica o aluno pelo WhatsApp de que seu e-mail foi verificado.
    """
    try:
        from apps.bot.models import BotConfiguration, ConversationState
        from apps.bot.state_machine import STATE_IDLE, apply_state_transition
        from apps.users.models import UserProfile
        from infra.waha.client import WahaClient

        profile = UserProfile.objects.get(pk=user_profile_id)
        if not profile.is_authenticated_utfpr or not profile.email_verified:
            return {"status": "skipped", "reason": "not_confirmed"}

        # Reseta estado preso em waiting_confirmation.
        conv, _ = ConversationState.objects.get_or_create(user=profile)
        apply_state_transition(conversation_state=conv, next_state=STATE_IDLE, clear_flow_data=True)

        waha_settings = BotConfiguration.get_active()
        client = WahaClient(settings=waha_settings)
        client.send_message(
            profile.phone_number,
            f"✅ *E-mail confirmado!*\n\n"
            f"Seu e-mail `{profile.email}` foi verificado com sucesso.\n\n"
            f"Agora você tem acesso completo ao IterBot.\n\n"
            f"Digite *menu* para ver as opções disponíveis.",
        )
        logger.info("student_confirmed_whatsapp_sent", user_id=user_profile_id)
        return {"status": "sent", "user_id": user_profile_id}
    except Exception as exc:
        logger.error(
            "student_confirmed_whatsapp_failed",
            user_id=user_profile_id,
            error=str(exc),
            exc_info=True,
        )
        raise self.retry(exc=exc) from exc


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
