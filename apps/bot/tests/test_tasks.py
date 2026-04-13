"""Testes para apps/bot/tasks.py — Health check e reconexão WAHA.

Cobre STAB-01 (beat schedule), STAB-02 (reconexão), STAB-03 (alerta e-mail).
"""
from unittest.mock import MagicMock, call, patch

import pytest


class TestBeatScheduleRegistration:
    """STAB-01: Verifica que a task está registrada no beat schedule."""

    def test_check_waha_health_in_beat_schedule(self):
        """STAB-01: 'check-waha-health' deve estar no CELERY_BEAT_SCHEDULE."""
        import django
        import os
        os.environ.setdefault("DJANGO_SETTINGS_MODULE", "waha_bot.settings")
        django.setup()
        from django.conf import settings
        assert "check-waha-health" in settings.CELERY_BEAT_SCHEDULE
        entry = settings.CELERY_BEAT_SCHEDULE["check-waha-health"]
        assert entry["task"] == "apps.bot.tasks.check_waha_health"

    def test_check_waha_health_schedule_is_5_minutes(self):
        """STAB-01: Schedule deve ser a cada 5 minutos."""
        from django.conf import settings
        from celery.schedules import crontab
        entry = settings.CELERY_BEAT_SCHEDULE["check-waha-health"]
        schedule = entry["schedule"]
        # Verificar que a schedule é um crontab com minute="*/5"
        assert hasattr(schedule, "_orig_minute")
        assert str(schedule._orig_minute) == "*/5"

    def test_clean_old_health_checks_in_beat_schedule(self):
        """Limpeza periódica deve estar no CELERY_BEAT_SCHEDULE."""
        from django.conf import settings
        assert "clean-old-health-checks" in settings.CELERY_BEAT_SCHEDULE
        entry = settings.CELERY_BEAT_SCHEDULE["clean-old-health-checks"]
        assert entry["task"] == "apps.bot.tasks.clean_old_health_checks"


class TestCheckWahaHealthTask:
    """STAB-01 / STAB-02 / STAB-03: Testa a task principal de health check."""

    @patch("apps.bot.tasks.cache")
    @patch("apps.bot.health.BotHealthMonitor")
    @patch("config.env.settings")
    def test_task_calls_check_bot_status(self, mock_settings, mock_monitor_cls, mock_cache):
        """STAB-01: Task deve chamar BotHealthMonitor().check_bot_status()."""
        mock_settings.waha.session_name = "default"
        mock_cache.get.return_value = {"status": "online"}
        mock_monitor = MagicMock()
        mock_monitor.check_bot_status.return_value = {
            "status": "online",
            "session_status": "WORKING",
            "response_time": 45.2,
            "error_message": None,
        }
        mock_monitor_cls.return_value = mock_monitor

        from apps.bot.tasks import check_waha_health
        # Chamar a task diretamente (sem Celery broker)
        result = check_waha_health()

        mock_monitor.check_bot_status.assert_called_once()

    @patch("apps.bot.tasks._send_offline_alert")
    @patch("apps.bot.tasks._attempt_reconnect")
    @patch("apps.bot.tasks.cache")
    def test_no_reconnect_when_prev_was_ok(
        self, mock_cache, mock_reconnect, mock_alert
    ):
        """STAB-02: Não deve tentar reconexão quando check anterior estava ok."""
        mock_cache.get.return_value = {"status": "online"}

        with patch("apps.bot.health.BotHealthMonitor") as mock_monitor_cls, \
             patch("config.env.settings") as mock_settings:
            mock_settings.waha.session_name = "default"
            mock_monitor = MagicMock()
            mock_monitor.check_bot_status.return_value = {
                "status": "offline",
                "session_status": "STOPPED",
                "response_time": None,
                "error_message": "Conexão recusada",
            }
            mock_monitor_cls.return_value = mock_monitor

            from apps.bot.tasks import check_waha_health
            check_waha_health()

        # Primeira falha: não aciona reconexão nem alerta
        mock_reconnect.assert_not_called()
        mock_alert.assert_not_called()

    @patch("apps.bot.tasks._send_offline_alert")
    @patch("apps.bot.tasks._attempt_reconnect", return_value=False)
    @patch("apps.bot.tasks.cache")
    def test_reconnect_triggered_on_consecutive_failures(
        self, mock_cache, mock_reconnect, mock_alert
    ):
        """STAB-02: Reconexão deve ser acionada após 2 checks consecutivos com falha."""
        # Simular que o check anterior também estava offline
        mock_cache.get.return_value = {"status": "offline"}

        with patch("apps.bot.health.BotHealthMonitor") as mock_monitor_cls, \
             patch("config.env.settings") as mock_settings:
            mock_settings.waha.session_name = "default"
            mock_monitor = MagicMock()
            mock_monitor.check_bot_status.return_value = {
                "status": "offline",
                "session_status": "STOPPED",
                "response_time": None,
                "error_message": "Conexão recusada",
            }
            mock_monitor_cls.return_value = mock_monitor

            from apps.bot.tasks import check_waha_health
            check_waha_health()

        # Segunda falha consecutiva: deve acionar reconexão e alerta
        mock_reconnect.assert_called_once()
        mock_alert.assert_called_once()

    @patch("apps.bot.tasks._send_offline_alert")
    @patch("apps.bot.tasks._attempt_reconnect", return_value=False)
    @patch("apps.bot.tasks.cache")
    def test_alert_only_sent_on_consecutive_failures(
        self, mock_cache, mock_reconnect, mock_alert
    ):
        """STAB-03: Alerta de e-mail deve ser enviado apenas na 2ª falha consecutiva."""
        # Simular check anterior offline → 2ª falha consecutiva
        mock_cache.get.return_value = {"status": "error"}

        with patch("apps.bot.health.BotHealthMonitor") as mock_monitor_cls, \
             patch("config.env.settings") as mock_settings:
            mock_settings.waha.session_name = "default"
            mock_monitor = MagicMock()
            mock_monitor.check_bot_status.return_value = {
                "status": "error",
                "session_status": "FAILED",
                "response_time": None,
                "error_message": "Timeout",
            }
            mock_monitor_cls.return_value = mock_monitor

            from apps.bot.tasks import check_waha_health
            check_waha_health()

        # Alerta deve ser enviado na 2ª falha consecutiva
        mock_alert.assert_called_once()


class TestAttemptReconnect:
    """STAB-02: Testa a função de reconexão com backoff."""

    @patch("apps.bot.tasks.time.sleep")
    def test_reconnect_backoff_values(self, mock_sleep):
        """STAB-02: Backoff deve ser 30s, 60s entre tentativas (não após a última)."""
        from apps.bot.tasks import RECONNECT_BACKOFF
        assert RECONNECT_BACKOFF == [30, 60, 120]

    @patch("apps.bot.tasks.time.sleep")
    def test_attempt_reconnect_returns_true_on_first_success(self, mock_sleep):
        """STAB-02: _attempt_reconnect retorna True quando start_session succeeds."""
        with patch("infra.waha.client.WahaClient") as mock_client_cls, \
             patch("apps.bot.models.BotConfiguration") as mock_config:
            mock_config.get_active.return_value = MagicMock()
            mock_client = MagicMock()
            mock_client.start_session.return_value = True
            mock_client_cls.return_value = mock_client

            from apps.bot.tasks import _attempt_reconnect
            result = _attempt_reconnect("test-session")

        assert result is True
        mock_client.start_session.assert_called_once()
        mock_sleep.assert_not_called()  # Não deve dormir após sucesso na 1ª tentativa

    @patch("apps.bot.tasks.time.sleep")
    def test_attempt_reconnect_returns_false_after_all_failures(self, mock_sleep):
        """STAB-02: _attempt_reconnect retorna False após 3 tentativas sem sucesso."""
        with patch("infra.waha.client.WahaClient") as mock_client_cls, \
             patch("apps.bot.models.BotConfiguration") as mock_config:
            mock_config.get_active.return_value = MagicMock()
            mock_client = MagicMock()
            mock_client.start_session.return_value = False
            mock_client_cls.return_value = mock_client

            from apps.bot.tasks import _attempt_reconnect
            result = _attempt_reconnect("test-session")

        assert result is False
        assert mock_client.start_session.call_count == 3

    @patch("apps.bot.tasks.time.sleep")
    def test_attempt_reconnect_sleeps_between_attempts(self, mock_sleep):
        """STAB-02: Deve dormir 30s e 60s entre as tentativas (não após a 3ª)."""
        with patch("infra.waha.client.WahaClient") as mock_client_cls, \
             patch("apps.bot.models.BotConfiguration") as mock_config:
            mock_config.get_active.return_value = MagicMock()
            mock_client = MagicMock()
            mock_client.start_session.return_value = False
            mock_client_cls.return_value = mock_client

            from apps.bot.tasks import _attempt_reconnect
            _attempt_reconnect("test-session")

        # Deve dormir entre tentativas 1→2 e 2→3, mas NÃO após a tentativa 3
        assert mock_sleep.call_count == 2
        mock_sleep.assert_any_call(30)
        mock_sleep.assert_any_call(60)


class TestSendOfflineAlert:
    """STAB-03: Testa o envio de alerta por e-mail."""

    @patch("apps.bot.tasks.send_mail")
    def test_alert_sent_to_correct_recipient(self, mock_send_mail):
        """STAB-03: E-mail deve ser enviado para bonruque@alunos.utfpr.edu.br."""
        from apps.bot.tasks import _send_offline_alert, ALERT_EMAIL
        _send_offline_alert(
            session_name="default",
            current_status="offline",
        )
        mock_send_mail.assert_called_once()
        call_kwargs = mock_send_mail.call_args
        assert ALERT_EMAIL in call_kwargs.kwargs.get(
            "recipient_list", call_kwargs.args[3] if len(call_kwargs.args) > 3 else []
        )

    @patch("apps.bot.tasks.send_mail")
    def test_alert_subject_contains_expected_text(self, mock_send_mail):
        """STAB-03: Assunto do e-mail deve conter identificação correta."""
        from apps.bot.tasks import _send_offline_alert, ALERT_SUBJECT
        _send_offline_alert(
            session_name="default",
            current_status="offline",
        )
        mock_send_mail.assert_called_once()
        call_args = mock_send_mail.call_args
        subject = call_args.kwargs.get("subject", call_args.args[0] if call_args.args else "")
        assert "CapyVagas" in subject
        assert "offline" in subject.lower() or "Bot WhatsApp" in subject

    @patch("apps.bot.tasks.send_mail")
    def test_alert_uses_fail_silently(self, mock_send_mail):
        """STAB-03: E-mail deve usar fail_silently=True para não bloquear o worker."""
        from apps.bot.tasks import _send_offline_alert
        _send_offline_alert(
            session_name="default",
            current_status="error",
            error_message="Timeout",
        )
        mock_send_mail.assert_called_once()
        call_kwargs = mock_send_mail.call_args.kwargs
        assert call_kwargs.get("fail_silently") is True


class TestCleanOldHealthChecks:
    """Testa a task de limpeza periódica."""

    def test_clean_task_calls_monitor(self):
        """Task de limpeza deve chamar BotHealthMonitor.clean_old_health_checks(days=7)."""
        with patch("apps.bot.health.BotHealthMonitor") as mock_monitor_cls:
            mock_monitor = MagicMock()
            mock_monitor.clean_old_health_checks.return_value = 42
            mock_monitor_cls.return_value = mock_monitor

            from apps.bot.tasks import clean_old_health_checks
            result = clean_old_health_checks()

        mock_monitor.clean_old_health_checks.assert_called_once_with(days=7)
        assert result["deleted_count"] == 42
