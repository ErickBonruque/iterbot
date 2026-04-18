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
