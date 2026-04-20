"""Testes para apps/bot/tasks.py apos refatoracao para wrappers thin."""

from unittest.mock import MagicMock, patch


class TestBeatScheduleRegistration:
    def test_check_waha_health_in_beat_schedule(self):
        import os

        import django

        os.environ.setdefault("DJANGO_SETTINGS_MODULE", "waha_bot.settings")
        django.setup()
        from django.conf import settings

        assert "check-waha-health" in settings.CELERY_BEAT_SCHEDULE
        entry = settings.CELERY_BEAT_SCHEDULE["check-waha-health"]
        assert entry["task"] == "apps.bot.tasks.check_waha_health"

    def test_check_waha_health_schedule_is_5_minutes(self):
        from django.conf import settings

        entry = settings.CELERY_BEAT_SCHEDULE["check-waha-health"]
        schedule = entry["schedule"]
        assert hasattr(schedule, "_orig_minute")
        assert str(schedule._orig_minute) == "*/5"


class TestCheckWahaHealthTask:
    @patch("apps.bot.health.BotHealthMonitor")
    def test_task_delegates_to_check_and_reconnect(self, mock_monitor_cls):
        mock_monitor = MagicMock()
        mock_monitor.check_and_reconnect.return_value = {
            "status": "online",
            "session_status": "WORKING",
            "prev_was_ok": True,
            "curr_is_ok": True,
        }
        mock_monitor_cls.return_value = mock_monitor

        from apps.bot.tasks import check_waha_health

        result = check_waha_health()

        mock_monitor.check_and_reconnect.assert_called_once()
        assert result["status"] == "online"


class TestHealthMonitorReconnectFlow:
    @patch("apps.bot.health.time.sleep")
    @patch("infra.waha.client.WahaClient")
    @patch("apps.bot.models.BotConfiguration")
    def test_attempt_reconnect_uses_expected_backoff(
        self, mock_config, mock_client_cls, mock_sleep
    ):
        from apps.bot.health import BotHealthMonitor

        mock_config.get_active.return_value = MagicMock()
        mock_client = MagicMock()
        mock_client.start_session.return_value = False
        mock_client_cls.return_value = mock_client

        monitor = BotHealthMonitor()
        result = monitor.attempt_reconnect()

        assert result is False
        assert mock_client.start_session.call_count == 3
        mock_sleep.assert_any_call(30)
        mock_sleep.assert_any_call(60)

    @patch("apps.bot.email_service.send_offline_alert_email")
    @patch("apps.bot.health.BotHealthMonitor.attempt_reconnect", return_value=False)
    @patch("apps.bot.health.BotHealthMonitor.check_bot_status")
    @patch("apps.bot.health.cache")
    def test_check_and_reconnect_alerts_after_two_failures(
        self, mock_cache, mock_check_status, _mock_reconnect, mock_alert
    ):
        from apps.bot.health import BotHealthMonitor

        mock_cache.get.return_value = {"status": "offline"}
        mock_check_status.return_value = {
            "status": "offline",
            "session_status": "STOPPED",
            "error_message": "Conexao recusada",
            "response_time": None,
        }

        monitor = BotHealthMonitor(session_name="default")
        monitor.check_and_reconnect()

        mock_alert.assert_called_once()


class TestSendConfirmationTask:
    @patch("apps.bot.tasks.send_confirmation_email_to_user")
    def test_send_confirmation_email_delegates_to_service(self, mock_service):
        mock_service.return_value = {"status": "sent", "user_id": 10, "email": "x@utfpr.edu"}

        from apps.bot.tasks import send_confirmation_email

        result = send_confirmation_email(user_id=10)

        mock_service.assert_called_once_with(10)
        assert result["status"] == "sent"


class TestEmailService:
    @patch("apps.bot.email_service.send_mail")
    def test_offline_alert_uses_fail_silently(self, mock_send_mail):
        from apps.bot.email_service import send_offline_alert_email

        send_offline_alert_email(
            session_name="default",
            current_status="offline",
            reconnect_attempted=True,
            reconnect_success=False,
        )

        mock_send_mail.assert_called_once()
        assert mock_send_mail.call_args.kwargs.get("fail_silently") is True
