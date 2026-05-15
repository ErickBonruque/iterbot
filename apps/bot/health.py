"""Sistema de health check e monitoramento do bot WAHA."""

from datetime import timedelta
from typing import ClassVar

import requests
import structlog
from django.core.cache import cache
from django.db.models import Avg
from django.utils import timezone

from apps.bot.models import BotHealthCheck
from config.env import settings

logger = structlog.get_logger(__name__)


class BotHealthMonitor:
    """Monitora a saude e performance do bot WAHA."""

    reconnect_backoff: ClassVar[list[int]] = [30, 60, 120]

    def __init__(self, waha_url=None, session_name=None):
        self.waha_url = waha_url or settings.waha.base_url
        self.session_name = session_name or settings.waha.session_name
        self.api_key = settings.waha.api_key

    def check_bot_status(self):
        """Verifica o status do bot WAHA e registra metricas."""
        import time

        start_time = time.time()
        result = {
            "status": "offline",
            "response_time": None,
            "session_status": "unknown",
            "last_check": timezone.now(),
            "error_message": None,
        }

        try:
            headers = {}
            if self.api_key:
                headers["X-Api-Key"] = self.api_key

            response = requests.get(
                f"{self.waha_url}/api/sessions/{self.session_name}", headers=headers, timeout=5
            )

            response_time = (time.time() - start_time) * 1000
            result["response_time"] = round(response_time, 2)

            if response.status_code == 200:
                data = response.json()
                result["status"] = "online" if data.get("status") == "WORKING" else "offline"
                result["session_status"] = data.get("status", "unknown")
            else:
                result["status"] = "error"
                result["error_message"] = f"HTTP {response.status_code}"

        except requests.exceptions.Timeout:
            result["status"] = "error"
            result["error_message"] = "Timeout ao conectar com WAHA"
            result["response_time"] = 5000.0

        except requests.exceptions.ConnectionError:
            result["status"] = "offline"
            result["error_message"] = "Nao foi possivel conectar ao servico WAHA"

        except Exception as exc:
            result["status"] = "error"
            result["error_message"] = str(exc)
            logger.error(
                "health_check_error",
                session_name=self.session_name,
                error=str(exc),
            )

        BotHealthCheck.objects.create(
            status=result["status"],
            response_time=result["response_time"],
            error_message=result["error_message"],
            session_status=result["session_status"],
        )

        cache.set("bot_last_status", result, timeout=60)
        return result

    def attempt_reconnect(self, attempt: int = 1) -> bool:
        """Tenta reconectar a sessao WAHA. Usa Celery retry com countdown em vez de sleep."""
        from apps.bot.models import BotConfiguration
        from infra.waha.client import WahaClient

        waha_settings = BotConfiguration.get_active()
        client = WahaClient(settings=waha_settings)

        logger.info(
            "waha_reconnect_attempt",
            session_name=self.session_name,
            attempt=attempt,
            max_attempts=len(self.reconnect_backoff),
        )

        try:
            if client.start_session():
                logger.info(
                    "waha_reconnect_success",
                    session_name=self.session_name,
                    attempt=attempt,
                )
                return True
        except Exception as exc:
            logger.error(
                "waha_reconnect_attempt_exception",
                session_name=self.session_name,
                attempt=attempt,
                error=str(exc),
            )

        logger.warning(
            "waha_reconnect_attempt_failed",
            session_name=self.session_name,
            attempt=attempt,
        )

        # Schedule next attempt via Celery task with countdown instead of blocking sleep
        if attempt < len(self.reconnect_backoff):
            from apps.bot.tasks import attempt_waha_reconnect

            countdown = self.reconnect_backoff[attempt - 1]
            attempt_waha_reconnect.apply_async(
                kwargs={"attempt": attempt + 1},
                countdown=countdown,
            )
            logger.info(
                "waha_reconnect_scheduled",
                session_name=self.session_name,
                next_attempt=attempt + 1,
                countdown_seconds=countdown,
            )
        else:
            logger.error(
                "waha_reconnect_all_attempts_failed",
                session_name=self.session_name,
                total_attempts=len(self.reconnect_backoff),
            )

        return False

    def check_and_reconnect(self) -> dict:
        """Executa health check e aplica threshold de 2 falhas consecutivas."""
        from apps.bot.email_service import send_offline_alert_email

        prev_status_data = cache.get("bot_last_status") or {}
        prev_is_ok = prev_status_data.get("status") == "online"

        current_result = self.check_bot_status()
        curr_is_ok = current_result["status"] == "online"

        logger.info(
            "waha_health_check_completed",
            session_name=self.session_name,
            status=current_result["status"],
            session_status=current_result.get("session_status", "unknown"),
            response_time_ms=current_result.get("response_time"),
            prev_was_ok=prev_is_ok,
        )

        if not prev_is_ok and not curr_is_ok:
            logger.warning(
                "waha_consecutive_failures_detected",
                session_name=self.session_name,
                current_status=current_result["status"],
            )

            reconnect_success = self.attempt_reconnect(attempt=1)
            send_offline_alert_email(
                session_name=self.session_name,
                current_status=current_result["status"],
                error_message=current_result.get("error_message"),
                reconnect_attempted=True,
                reconnect_success=reconnect_success,
            )
        elif prev_is_ok and not curr_is_ok:
            logger.info(
                "waha_first_failure_detected",
                session_name=self.session_name,
                current_status=current_result["status"],
                note="Aguardando proximo ciclo para confirmar falha consecutiva",
            )

        return {
            "status": current_result["status"],
            "session_status": current_result.get("session_status", "unknown"),
            "prev_was_ok": prev_is_ok,
            "curr_is_ok": curr_is_ok,
        }

    def get_metrics_summary(self, hours=24):
        """Obtem resumo das metricas do bot nas ultimas N horas."""
        since = timezone.now() - timedelta(hours=hours)
        checks = BotHealthCheck.objects.filter(created_at__gte=since)

        total = checks.count()
        if total == 0:
            return {
                "uptime_percentage": 0,
                "avg_response_time": 0,
                "total_checks": 0,
                "error_count": 0,
                "last_error": None,
            }

        online_count = checks.filter(status="online").count()
        error_count = checks.exclude(status="online").count()

        valid_checks = checks.filter(response_time__isnull=False, response_time__lt=5000)
        avg_response = valid_checks.aggregate(Avg("response_time"))["response_time__avg"] or 0

        last_error_check = (
            checks.filter(error_message__isnull=False).order_by("-created_at").first()
        )

        return {
            "uptime_percentage": round((online_count / total) * 100, 2),
            "avg_response_time": round(avg_response, 2),
            "total_checks": total,
            "error_count": error_count,
            "last_error": last_error_check.error_message if last_error_check else None,
        }

    def test_bot_now(self):
        """Executa um teste completo do bot."""
        status = self.check_bot_status()

        if status["status"] != "online":
            return {
                "success": False,
                "message": f"Bot nao esta online. Status: {status['session_status']}",
                "details": status,
            }

        return {"success": True, "message": "Bot esta operacional", "details": status}

    def clean_old_health_checks(self, days=90):
        """Remove registros de health check antigos."""
        cutoff = timezone.now() - timedelta(days=days)
        deleted_count = BotHealthCheck.objects.filter(created_at__lt=cutoff).delete()[0]
        logger.info(
            "health_checks_cleaned",
            deleted_count=deleted_count,
            days_threshold=days,
        )
        return deleted_count
