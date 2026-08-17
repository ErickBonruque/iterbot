from unittest.mock import MagicMock, patch

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
        settings = _make_settings(
            base_url="http://localhost:3000", api_key="token", session_name="session"
        )
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
        import inspect

        import infra.waha.client as client_module

        source = inspect.getsource(client_module)
        assert "structlog.get_logger" in source
        assert "logging.getLogger" not in source

    def test_api_key_not_in_log_events(self):
        """STAB-04 / Segurança: api_key nunca deve aparecer em eventos de log."""
        import inspect

        import infra.waha.client as client_module

        source = inspect.getsource(client_module)
        # api_key pode aparecer no cabeçalho HTTP mas não em chamadas de logger
        log_calls = [
            line for line in source.splitlines() if "logger." in line and "api_key" in line
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
            session_name="iterbot",
        )
        client = WahaClient(settings=settings)
        with patch("infra.waha.client.requests.post") as mock_post:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_post.return_value = mock_response
            client.start_session()
        call_url = mock_post.call_args[0][0]
        assert call_url == "http://waha:3000/api/sessions/iterbot/start"


class TestWahaClientLogoutSession:
    """Logout devolve a sessão para SCAN_QR_CODE (pareamento pelo admin)."""

    def test_posts_to_logout_endpoint(self):
        client = WahaClient(
            settings=_make_settings(base_url="http://waha:3000", session_name="iterbot")
        )
        with patch("infra.waha.client.requests.post") as mock_post:
            mock_post.return_value = MagicMock(status_code=200)
            assert client.logout_session() is True
        assert mock_post.call_args[0][0] == "http://waha:3000/api/sessions/iterbot/logout"

    def test_returns_false_on_http_error(self):
        client = WahaClient(settings=_make_settings())
        with patch("infra.waha.client.requests.post") as mock_post:
            mock_post.return_value = MagicMock(status_code=500)
            assert client.logout_session() is False

    def test_returns_false_on_connection_error(self):
        client = WahaClient(settings=_make_settings())
        with patch("infra.waha.client.requests.post") as mock_post:
            mock_post.side_effect = requests.exceptions.ConnectionError()
            assert client.logout_session() is False


class TestWahaClientGetQr:
    """QR de pareamento consumido pela tela Status do Bot."""

    def test_returns_data_uri_when_session_is_scanning(self):
        client = WahaClient(
            settings=_make_settings(base_url="http://waha:3000", session_name="iterbot")
        )
        with patch("infra.waha.client.requests.get") as mock_get:
            mock_get.return_value = MagicMock(
                status_code=200,
                headers={"Content-Type": "image/png"},
                content=b"ABC",
            )
            result = client.get_qr()

        assert result.available is True
        # "ABC" em base64 — a imagem vai inline no <img src> da tela do admin.
        assert result.image == "data:image/png;base64,QUJD"
        assert mock_get.call_args[0][0] == "http://waha:3000/api/iterbot/auth/qr"

    def test_reports_session_status_on_422(self):
        # O WAHA responde 422 quando a sessão não está em SCAN_QR_CODE; a tela
        # precisa do status para orientar o operador em vez de mostrar erro cru.
        client = WahaClient(settings=_make_settings())
        response = MagicMock(status_code=422, headers={"Content-Type": "application/json"})
        response.json.return_value = {
            "error": "Session status is not as expected",
            "status": "FAILED",
        }
        with patch("infra.waha.client.requests.get", return_value=response):
            result = client.get_qr()

        assert result.available is False
        assert result.session_status == "FAILED"
        assert result.error == "Session status is not as expected"

    def test_survives_non_json_error_body(self):
        client = WahaClient(settings=_make_settings())
        response = MagicMock(status_code=502, headers={"Content-Type": "text/html"})
        response.json.side_effect = ValueError("no json")
        with patch("infra.waha.client.requests.get", return_value=response):
            result = client.get_qr()

        assert result.available is False
        assert "502" in result.error

    def test_returns_error_when_waha_is_unreachable(self):
        client = WahaClient(settings=_make_settings())
        with patch("infra.waha.client.requests.get") as mock_get:
            mock_get.side_effect = requests.exceptions.ConnectionError()
            result = client.get_qr()

        assert result.available is False
        assert result.error
