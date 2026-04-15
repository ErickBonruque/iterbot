"""Tasks Celery para monitoramento e estabilidade do bot WhatsApp."""

import time

import structlog
from celery import shared_task
from django.core.cache import cache
from django.core.mail import send_mail

logger = structlog.get_logger(__name__)

# E-mail de alerta fixo — nao configuravel via admin neste milestone (D-05)
ALERT_EMAIL = "bonrqueruck@gmail.com"
ALERT_SUBJECT = "[CapyVagas] ⚠️ Bot WhatsApp offline"

# Backoff entre tentativas de reconexão em segundos (D-02)
RECONNECT_BACKOFF = [30, 60, 120]


@shared_task(bind=True, max_retries=0)
def check_waha_health(self) -> dict:
    """Verifica saúde da sessão WAHA e aciona reconexão se necessário.

    Executa a cada 5 minutos via Celery beat (STAB-01).
    Aciona reconexão após 2 checks consecutivos com falha (STAB-02).
    Envia alerta por e-mail ao admin na transição online→offline (STAB-03).
    """
    try:
        from apps.bot.health import BotHealthMonitor
        from config.env import settings

        session_name = settings.waha.session_name
        monitor = BotHealthMonitor()

        # Ler status anterior do Redis antes de executar o check atual (D-03)
        # cache.set('bot_last_status', result, timeout=60) é feito dentro de check_bot_status()
        prev_status_data = cache.get("bot_last_status") or {}
        prev_is_ok = prev_status_data.get("status") == "online"

        # Executar health check — salva BotHealthCheck no banco e atualiza cache
        current_result = monitor.check_bot_status()
        curr_is_ok = current_result["status"] == "online"

        logger.info(
            "waha_health_check_completed",
            session_name=session_name,
            status=current_result["status"],
            session_status=current_result.get("session_status", "unknown"),
            response_time_ms=current_result.get("response_time"),
            prev_was_ok=prev_is_ok,
        )

        # Lógica de threshold: 2 checks consecutivos com falha → reconectar + alertar (D-03, D-06)
        if not prev_is_ok and not curr_is_ok:
            logger.warning(
                "waha_consecutive_failures_detected",
                session_name=session_name,
                current_status=current_result["status"],
            )

            # Tentar reconexão automática (STAB-02)
            reconnect_success = _attempt_reconnect(session_name)

            # Enviar alerta por e-mail (STAB-03) — independente do resultado da reconexão
            _send_offline_alert(
                session_name=session_name,
                current_status=current_result["status"],
                error_message=current_result.get("error_message"),
                reconnect_attempted=True,
                reconnect_success=reconnect_success,
            )

        elif prev_is_ok and not curr_is_ok:
            # Primeira falha — registrar mas aguardar próximo ciclo antes de agir (D-06)
            logger.info(
                "waha_first_failure_detected",
                session_name=session_name,
                current_status=current_result["status"],
                note="Aguardando próximo ciclo para confirmar falha consecutiva",
            )

        return {
            "status": current_result["status"],
            "session_status": current_result.get("session_status", "unknown"),
            "prev_was_ok": prev_is_ok,
            "curr_is_ok": curr_is_ok,
        }

    except Exception as exc:
        logger.error(
            "waha_health_check_task_failed",
            error=str(exc),
            exc_info=True,
        )
        # Nunca re-raise — não deixar exception travar o worker Celery
        return {"status": "error", "error": str(exc)}


def _attempt_reconnect(session_name: str) -> bool:
    """Tenta reconectar a sessão WAHA com backoff crescente.

    Realiza até 3 tentativas com espera de 30s, 60s e 120s entre elas.
    Retorna True se alguma tentativa tiver sucesso, False caso contrário.
    """
    from infra.waha.client import WahaClient
    from apps.bot.models import BotConfiguration

    waha_settings = BotConfiguration.get_active()
    client = WahaClient(settings=waha_settings)

    for attempt, backoff_seconds in enumerate(RECONNECT_BACKOFF, start=1):
        try:
            logger.info(
                "waha_reconnect_attempt",
                session_name=session_name,
                attempt=attempt,
                max_attempts=len(RECONNECT_BACKOFF),
            )

            success = client.start_session()

            if success:
                logger.info(
                    "waha_reconnect_success",
                    session_name=session_name,
                    attempt=attempt,
                )
                return True

            logger.warning(
                "waha_reconnect_attempt_failed",
                session_name=session_name,
                attempt=attempt,
                backoff_seconds=backoff_seconds,
            )

        except Exception as exc:
            logger.error(
                "waha_reconnect_attempt_exception",
                session_name=session_name,
                attempt=attempt,
                error=str(exc),
            )

        # Aguardar antes da próxima tentativa (exceto após a última)
        if attempt < len(RECONNECT_BACKOFF):
            time.sleep(backoff_seconds)

    logger.error(
        "waha_reconnect_all_attempts_failed",
        session_name=session_name,
        total_attempts=len(RECONNECT_BACKOFF),
    )
    return False


def _send_offline_alert(
    session_name: str,
    current_status: str,
    error_message: str | None = None,
    reconnect_attempted: bool = False,
    reconnect_success: bool = False,
) -> None:
    """Envia e-mail de alerta ao admin quando bot fica offline.

    Usa fail_silently=True para nunca bloquear o worker Celery (D-05).
    """
    from django.conf import settings as django_settings

    body_lines = [
        f"O bot WhatsApp (sessão: {session_name}) foi detectado como OFFLINE.",
        "",
        f"Status atual: {current_status}",
    ]

    if error_message:
        body_lines.append(f"Mensagem de erro: {error_message}")

    if reconnect_attempted:
        reconnect_result = "✅ Reconexão bem-sucedida" if reconnect_success else "❌ Reconexão falhou após 3 tentativas"
        body_lines.append(f"Tentativa de reconexão automática: {reconnect_result}")

    body_lines.extend([
        "",
        "Verifique o painel administrativo para mais detalhes:",
        f"{getattr(django_settings, 'PORTAL_BASE_URL', 'http://localhost:8000')}/admin/bot/bothealthcheck/",
    ])

    message_body = "\n".join(body_lines)

    try:
        send_mail(
            subject=ALERT_SUBJECT,
            message=message_body,
            from_email=django_settings.DEFAULT_FROM_EMAIL,
            recipient_list=[ALERT_EMAIL],
            fail_silently=True,  # Nunca bloquear o worker por falha de e-mail
        )
        logger.info(
            "waha_offline_alert_sent",
            session_name=session_name,
            recipient=ALERT_EMAIL,
        )
    except Exception as exc:
        # fail_silently=True já cobre a maioria dos casos, mas capturamos por segurança
        logger.error(
            "waha_offline_alert_failed",
            session_name=session_name,
            error=str(exc),
        )


@shared_task(bind=True, max_retries=0)
def clean_old_health_checks(self) -> dict:
    """Remove registros BotHealthCheck com mais de 7 dias.

    Executado semanalmente via Celery beat (todo domingo às 02:00).
    """
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
