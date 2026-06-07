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

    def test_clean_old_health_checks_schedule_is_daily(self):
        from django.conf import settings

        entry = settings.CELERY_BEAT_SCHEDULE["clean-old-health-checks"]
        schedule = entry["schedule"]
        # daily = no day_of_week restriction (runs every day)
        assert str(schedule._orig_hour) == "2"
        assert str(schedule._orig_minute) == "0"
        # daily schedule has no day_of_week filter — uses default "*"
        assert str(schedule._orig_day_of_week) == "*"


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
    @patch("apps.bot.tasks.attempt_waha_reconnect")
    @patch("infra.waha.client.WahaClient")
    @patch("apps.bot.models.BotConfiguration")
    def test_attempt_reconnect_schedules_celery_retry_instead_of_sleep(
        self, mock_config, mock_client_cls, mock_reconnect_task
    ):
        """Verifica que attempt_reconnect usa Celery countdown em vez de time.sleep."""
        from apps.bot.health import BotHealthMonitor

        mock_config.get_active.return_value = MagicMock()
        mock_client = MagicMock()
        mock_client.start_session.return_value = False
        mock_client_cls.return_value = mock_client

        monitor = BotHealthMonitor()
        result = monitor.attempt_reconnect(attempt=1)

        assert result is False
        # Deve agendar próxima tentativa via Celery, não bloquear com sleep
        mock_reconnect_task.apply_async.assert_called_once_with(
            kwargs={"attempt": 2},
            countdown=30,
        )

    @patch("apps.bot.tasks.attempt_waha_reconnect")
    @patch("infra.waha.client.WahaClient")
    @patch("apps.bot.models.BotConfiguration")
    def test_attempt_reconnect_returns_true_on_success(
        self, mock_config, mock_client_cls, mock_reconnect_task
    ):
        from apps.bot.health import BotHealthMonitor

        mock_config.get_active.return_value = MagicMock()
        mock_client = MagicMock()
        mock_client.start_session.return_value = True
        mock_client_cls.return_value = mock_client

        monitor = BotHealthMonitor()
        result = monitor.attempt_reconnect(attempt=1)

        assert result is True
        mock_reconnect_task.apply_async.assert_not_called()

    @patch("apps.bot.tasks.attempt_waha_reconnect")
    @patch("infra.waha.client.WahaClient")
    @patch("apps.bot.models.BotConfiguration")
    def test_attempt_reconnect_last_attempt_does_not_schedule_more(
        self, mock_config, mock_client_cls, mock_reconnect_task
    ):
        from apps.bot.health import BotHealthMonitor

        mock_config.get_active.return_value = MagicMock()
        mock_client = MagicMock()
        mock_client.start_session.return_value = False
        mock_client_cls.return_value = mock_client

        monitor = BotHealthMonitor()
        # attempt=3 is the last one (reconnect_backoff has 3 entries)
        result = monitor.attempt_reconnect(attempt=3)

        assert result is False
        mock_reconnect_task.apply_async.assert_not_called()

    @patch("apps.bot.health.send_offline_alert_email")
    @patch("apps.bot.health.BotHealthMonitor.attempt_reconnect", return_value=False)
    @patch("apps.bot.health.BotHealthMonitor.check_bot_status")
    @patch("apps.bot.health.cache")
    def test_check_and_reconnect_alerts_after_two_failures(
        self, mock_cache, mock_check_status, _mock_reconnect, mock_alert
    ):
        from apps.bot.health import BotHealthMonitor

        offline_status = {"status": "offline"}
        mock_cache.get.side_effect = lambda key: (
            None if key == "waha_alert_sent" else offline_status
        )
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
    @patch("apps.bot.email_service.send_confirmation_email_to_user")
    def test_send_confirmation_email_delegates_to_service(self, mock_service):
        mock_service.return_value = {"status": "sent", "user_id": 10, "email": "x@utfpr.edu"}

        from apps.bot.tasks import send_confirmation_email

        result = send_confirmation_email(user_id=10)

        mock_service.assert_called_once_with(10)
        assert result["status"] == "sent"


class TestEmailService:
    @patch("apps.bot.email_service.send_transactional_email")
    def test_offline_alert_delegates_to_transactional_email(self, mock_send):
        mock_send.return_value = {"status": "sent", "provider": "resend", "message_id": "test-id"}

        from apps.bot.email_service import send_offline_alert_email

        send_offline_alert_email(
            session_name="default",
            current_status="offline",
            reconnect_attempted=True,
            reconnect_success=False,
        )

        mock_send.assert_called_once()
        assert mock_send.call_args.kwargs.get("event_type") == "offline_alert"
