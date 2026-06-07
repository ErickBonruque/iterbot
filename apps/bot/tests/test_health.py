"""Testes para apps/bot/health.py — BotHealthMonitor (STAB-04)."""

from unittest.mock import MagicMock, patch


class TestBotHealthMonitorStructlog:
    """Verifica que health.py usa structlog (e não logging padrão)."""

    def test_health_module_uses_structlog(self):
        """STAB-04: health.py deve importar structlog, não logging."""
        import inspect

        import apps.bot.health as health_module

        source = inspect.getsource(health_module)
        assert "structlog.get_logger" in source
        assert "logging.getLogger" not in source

    def test_check_bot_status_returns_dict(self):
        """STAB-01: check_bot_status() deve retornar dict com campos obrigatórios."""
        from apps.bot.health import BotHealthMonitor

        monitor = BotHealthMonitor(
            waha_url="http://localhost:3000",
            session_name="test-session",
        )
        with patch("apps.bot.health.requests.get") as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"status": "WORKING"}
            mock_get.return_value = mock_response
            with (
                patch("apps.bot.health.BotHealthCheck.objects.create"),
                patch("apps.bot.health.cache.set"),
            ):
                result = monitor.check_bot_status()
        assert "status" in result
        assert "session_status" in result
        assert "response_time" in result
        assert "error_message" in result

    def test_check_bot_status_working_returns_online(self):
        """STAB-01: sessão WORKING deve resultar em status 'online'."""
        from apps.bot.health import BotHealthMonitor

        monitor = BotHealthMonitor(
            waha_url="http://localhost:3000",
            session_name="test-session",
        )
        with patch("apps.bot.health.requests.get") as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"status": "WORKING"}
            mock_get.return_value = mock_response
            with (
                patch("apps.bot.health.BotHealthCheck.objects.create"),
                patch("apps.bot.health.cache.set"),
            ):
                result = monitor.check_bot_status()
        assert result["status"] == "online"

    def test_check_bot_status_non_working_returns_offline(self):
        """STAB-01: sessão não-WORKING deve resultar em status 'offline'."""
        from apps.bot.health import BotHealthMonitor

        monitor = BotHealthMonitor(
            waha_url="http://localhost:3000",
            session_name="test-session",
        )
        with patch("apps.bot.health.requests.get") as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"status": "STOPPED"}
            mock_get.return_value = mock_response
            with (
                patch("apps.bot.health.BotHealthCheck.objects.create"),
                patch("apps.bot.health.cache.set"),
            ):
                result = monitor.check_bot_status()
        assert result["status"] == "offline"


class TestAlertThrottle:
    """WAHA-02: Throttle de alertas de email via Redis cache."""

    def _make_monitor(self):
        from apps.bot.health import BotHealthMonitor

        return BotHealthMonitor(waha_url="http://localhost:3000", session_name="test")

    def test_throttle_skips_second_alert_within_30min(self):
        """Segundo alerta dentro de 30min deve ser suprimido (cache key existe)."""
        from unittest.mock import patch

        monitor = self._make_monitor()
        # Simular dois checks consecutivos OFFLINE
        offline_status = {
            "status": "offline",
            "session_status": "STOPPED",
            "response_time": None,
            "error_message": "timeout",
            "last_check": None,
        }

        with (
            patch("apps.bot.health.BotHealthMonitor.check_bot_status", return_value=offline_status),
            patch("apps.bot.health.BotHealthMonitor.attempt_reconnect", return_value=False),
            patch("apps.bot.health.cache") as mock_cache,
            patch("apps.bot.health.send_offline_alert_email") as mock_email,
        ):
            # Primeira chamada: cache vazio → prev_is_ok=False, curr_is_ok=False
            mock_cache.get.side_effect = lambda key: (
                None
                if key == "waha_alert_sent"
                else offline_status
                if key == "bot_last_status"
                else None
            )
            monitor.check_and_reconnect()

            # Simular que a chave existe agora (throttle ativo)
            mock_cache.get.side_effect = lambda key: (
                True
                if key == "waha_alert_sent"
                else offline_status
                if key == "bot_last_status"
                else None
            )
            mock_email.reset_mock()
            monitor.check_and_reconnect()

        # Segunda chamada NÃO deve ter enviado email
        mock_email.assert_not_called()

    def test_throttle_sends_alert_after_cooldown_expires(self):
        """Quando cache key não existe (expirou), alerta deve ser enviado."""
        from unittest.mock import patch

        monitor = self._make_monitor()
        offline_status = {
            "status": "offline",
            "session_status": "STOPPED",
            "response_time": None,
            "error_message": "timeout",
            "last_check": None,
        }

        with (
            patch("apps.bot.health.BotHealthMonitor.check_bot_status", return_value=offline_status),
            patch("apps.bot.health.BotHealthMonitor.attempt_reconnect", return_value=False),
            patch("apps.bot.health.cache") as mock_cache,
            patch("apps.bot.health.send_offline_alert_email") as mock_email,
        ):
            mock_cache.get.side_effect = lambda key: (
                None
                if key == "waha_alert_sent"
                else offline_status
                if key == "bot_last_status"
                else None
            )
            monitor.check_and_reconnect()

        mock_email.assert_called_once()

    def test_redis_key_ttl_is_1800s(self):
        """cache.set('waha_alert_sent', True, timeout=1800) deve ser chamado ao enviar alerta."""
        from unittest.mock import call, patch

        monitor = self._make_monitor()
        offline_status = {
            "status": "offline",
            "session_status": "STOPPED",
            "response_time": None,
            "error_message": "timeout",
            "last_check": None,
        }

        with (
            patch("apps.bot.health.BotHealthMonitor.check_bot_status", return_value=offline_status),
            patch("apps.bot.health.BotHealthMonitor.attempt_reconnect", return_value=False),
            patch("apps.bot.health.cache") as mock_cache,
            patch("apps.bot.health.send_offline_alert_email"),
        ):
            mock_cache.get.side_effect = lambda key: (
                None
                if key == "waha_alert_sent"
                else offline_status
                if key == "bot_last_status"
                else None
            )
            monitor.check_and_reconnect()

        # Verificar que cache.set foi chamado com a chave e TTL corretos
        throttle_calls = [
            c for c in mock_cache.set.call_args_list if c.args and c.args[0] == "waha_alert_sent"
        ]
        assert len(throttle_calls) == 1
        assert throttle_calls[0] == call("waha_alert_sent", True, timeout=1800)
