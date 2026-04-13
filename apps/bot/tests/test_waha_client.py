from unittest.mock import patch, MagicMock

import pytest
import requests

from django.test import TestCase

from config.env import WahaSettings
from infra.waha.client import WahaClient


def _make_settings(
    base_url="http://localhost:3000",
    api_key="test-key",
    session_name="default",
    timeout_seconds=5,
) -> WahaSettings:
    """Cria WahaSettings com valores de teste sem ler .env."""
    s = WahaSettings.__new__(WahaSettings)
    s.base_url = base_url
    s.api_key = api_key
    s.session_name = session_name
    s.timeout_seconds = timeout_seconds
    return s


class WahaClientTests(TestCase):
    def test_send_message_success(self):
        settings = WahaSettings(base_url="http://localhost:3000", api_key="token", session_name="session")
        client = WahaClient(settings=settings)

        with patch("infra.waha.client.requests.post") as post_mock:
            post_mock.return_value.status_code = 200
            result = client.send_message("5511999999999", "hello")

        self.assertTrue(result)
        post_mock.assert_called_once()
        payload = post_mock.call_args.kwargs["json"]
        self.assertEqual(payload["chatId"], "5511999999999@c.us")

    def test_send_message_failure_logs_error(self):
        client = WahaClient()

        with patch("infra.waha.client.requests.post") as post_mock:
            post_mock.return_value.status_code = 500
            result = client.send_message("5511999999999@c.us", "hello")

        self.assertFalse(result)


class TestWahaClientStructlog:
    """Verifica que client.py usa structlog (STAB-04)."""

    def test_client_module_uses_structlog(self):
        """STAB-04: infra/waha/client.py deve importar structlog, não logging."""
        import infra.waha.client as client_module
        import inspect
        source = inspect.getsource(client_module)
        assert "structlog.get_logger" in source
        assert "logging.getLogger" not in source

    def test_api_key_not_in_log_events(self):
        """STAB-04 / Segurança: api_key nunca deve aparecer em eventos de log."""
        import infra.waha.client as client_module
        import inspect
        source = inspect.getsource(client_module)
        # api_key pode aparecer no cabeçalho HTTP mas não em chamadas de logger
        log_calls = [
            line for line in source.splitlines()
            if "logger." in line and "api_key" in line
        ]
        assert log_calls == [], f"api_key encontrado em chamada de log: {log_calls}"


class TestWahaClientStartSession:
    """Testes para o método start_session() (STAB-01)."""

    def test_start_session_exists(self):
        """STAB-01: WahaClient deve ter método start_session."""
        assert hasattr(WahaClient, "start_session")

    def test_start_session_returns_true_on_success(self):
        """STAB-01: start_session() retorna True quando API responde 200."""
        settings = _make_settings()
        client = WahaClient(settings=settings)
        with patch("infra.waha.client.requests.post") as mock_post:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_post.return_value = mock_response
            result = client.start_session()
        assert result is True
        mock_post.assert_called_once_with(
            "http://localhost:3000/api/sessions/default/start",
            headers={"X-Api-Key": "test-key", "Content-Type": "application/json"},
            timeout=5,
        )

    def test_start_session_returns_false_on_http_error(self):
        """STAB-01: start_session() retorna False quando API responde 4xx/5xx."""
        settings = _make_settings()
        client = WahaClient(settings=settings)
        with patch("infra.waha.client.requests.post") as mock_post:
            mock_response = MagicMock()
            mock_response.status_code = 500
            mock_post.return_value = mock_response
            result = client.start_session()
        assert result is False

    def test_start_session_returns_false_on_timeout(self):
        """STAB-01: start_session() retorna False em timeout sem re-raise."""
        settings = _make_settings()
        client = WahaClient(settings=settings)
        with patch("infra.waha.client.requests.post") as mock_post:
            mock_post.side_effect = requests.exceptions.Timeout()
            result = client.start_session()
        assert result is False

    def test_start_session_returns_false_on_connection_error(self):
        """STAB-01: start_session() retorna False em ConnectionError sem re-raise."""
        settings = _make_settings()
        client = WahaClient(settings=settings)
        with patch("infra.waha.client.requests.post") as mock_post:
            mock_post.side_effect = requests.exceptions.ConnectionError()
            result = client.start_session()
        assert result is False

    def test_start_session_posts_to_correct_url(self):
        """STAB-01: URL do endpoint deve ser /api/sessions/{session_name}/start."""
        settings = _make_settings(
            base_url="http://waha:3000",
            session_name="capyvagas",
        )
        client = WahaClient(settings=settings)
        with patch("infra.waha.client.requests.post") as mock_post:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_post.return_value = mock_response
            client.start_session()
        call_url = mock_post.call_args[0][0]
        assert call_url == "http://waha:3000/api/sessions/capyvagas/start"
