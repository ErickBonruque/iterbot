"""Testes para endpoints admin WAHA — /admin/api/waha-status/ e /admin/api/waha-restart/.

WAHA-03: card de status em tempo real e botão de reconexão manual.
"""

import pytest
from django.contrib.auth import get_user_model
from django.test import Client


@pytest.fixture
def staff_client(db):
    """Client autenticado como staff."""
    user_model = get_user_model()
    user = user_model.objects.create_user(
        username="admin_test",
        password="testpass123",
        is_staff=True,
    )
    client = Client()
    client.force_login(user)
    return client


@pytest.fixture
def anon_client(db):
    """Client sem autenticação."""
    return Client()


@pytest.fixture
def non_staff_client(db):
    """Client autenticado mas sem is_staff."""
    user_model = get_user_model()
    user = user_model.objects.create_user(
        username="regular_user",
        password="testpass123",
        is_staff=False,
    )
    client = Client()
    client.force_login(user)
    return client


@pytest.mark.django_db
class TestWahaStatusEndpoint:
    """GET /admin/api/waha-status/ deve retornar JSON com campos obrigatórios."""

    def test_returns_json_with_required_fields(self, staff_client):
        """Resposta deve conter: status, session_status, response_time, last_check."""
        from unittest.mock import patch

        cached_status = {
            "status": "online",
            "session_status": "WORKING",
            "response_time": 120.5,
            "last_check": "2026-06-07T10:00:00",
            "error_message": None,
        }

        with patch("django.core.cache.cache.get", return_value=cached_status):
            response = staff_client.get("/admin/api/waha-status/")

        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "session_status" in data
        assert "response_time" in data
        assert "last_check" in data

    def test_anonymous_redirect(self, anon_client):
        """Requisição anônima deve receber redirect 302 para login."""
        response = anon_client.get("/admin/api/waha-status/")
        assert response.status_code == 302


@pytest.mark.django_db
class TestWahaRestartEndpoint:
    """POST /admin/api/waha-restart/ deve chamar WahaClient.start_session() e retornar JSON."""

    def test_returns_success_true_or_false(self, staff_client):
        """POST por staff retorna JsonResponse com chave 'success' (bool)."""
        from unittest.mock import patch

        with patch("infra.waha.client.WahaClient.start_session", return_value=True):
            response = staff_client.post(
                "/admin/api/waha-restart/",
                HTTP_X_REQUESTED_WITH="XMLHttpRequest",
            )

        assert response.status_code == 200
        data = response.json()
        assert "success" in data
        assert isinstance(data["success"], bool)

    def test_post_requires_staff(self, non_staff_client):
        """POST por usuário não-staff deve ser redirecionado (não 200)."""
        response = non_staff_client.post("/admin/api/waha-restart/")
        assert response.status_code == 302


@pytest.mark.django_db
class TestWahaQrEndpoint:
    """GET /admin/api/waha-qr/ alimenta o pareamento pela tela Status do Bot."""

    def test_returns_image_when_available(self, staff_client):
        from unittest.mock import patch

        from infra.waha.client import QrCodeResult

        qr = QrCodeResult(image="data:image/png;base64,QUJD")
        with patch("infra.waha.client.WahaClient.get_qr", return_value=qr):
            response = staff_client.get("/admin/api/waha-qr/")

        assert response.status_code == 200
        data = response.json()
        assert data["available"] is True
        assert data["image"] == "data:image/png;base64,QUJD"

    def test_reports_session_status_when_qr_unavailable(self, staff_client):
        from unittest.mock import patch

        from infra.waha.client import QrCodeResult

        qr = QrCodeResult(session_status="FAILED", error="Session status is not as expected")
        with patch("infra.waha.client.WahaClient.get_qr", return_value=qr):
            response = staff_client.get("/admin/api/waha-qr/")

        data = response.json()
        assert data["available"] is False
        assert data["image"] is None
        assert data["session_status"] == "FAILED"
        assert "not as expected" in data["error"]

    def test_requires_staff(self, non_staff_client):
        response = non_staff_client.get("/admin/api/waha-qr/")
        assert response.status_code == 302


@pytest.mark.django_db
class TestStatusBotPage:
    """A tela Status do Bot hospeda o pareamento por QR."""

    def test_renders_pairing_panel(self, staff_client):
        from unittest.mock import patch

        with patch("apps.bot.health.BotHealthMonitor.check_bot_status") as check:
            check.return_value = {
                "status": "offline",
                "response_time": None,
                "session_status": "FAILED",
                "last_check": None,
                "error_message": None,
            }
            response = staff_client.get("/admin/status-bot/")

        assert response.status_code == 200
        content = response.content.decode()
        assert 'id="waha-pairing"' in content
        assert "/admin/api/waha-qr/" in content


@pytest.mark.django_db
class TestWahaLogoutEndpoint:
    """POST /admin/api/waha-logout/ libera a sessão para um novo pareamento."""

    def test_logout_then_start(self, staff_client):
        from unittest.mock import patch

        with (
            patch("infra.waha.client.WahaClient.logout_session", return_value=True) as logout,
            patch("infra.waha.client.WahaClient.start_session", return_value=True) as start,
        ):
            response = staff_client.post(
                "/admin/api/waha-logout/",
                HTTP_X_REQUESTED_WITH="XMLHttpRequest",
            )

        assert response.json()["success"] is True
        logout.assert_called_once()
        # Sem o start a sessão fica parada e nunca chega a SCAN_QR_CODE.
        start.assert_called_once()

    def test_reports_failure_when_logout_refused(self, staff_client):
        from unittest.mock import patch

        with (
            patch("infra.waha.client.WahaClient.logout_session", return_value=False),
            patch("infra.waha.client.WahaClient.start_session") as start,
        ):
            response = staff_client.post("/admin/api/waha-logout/")

        assert response.json()["success"] is False
        start.assert_not_called()

    def test_rejects_get(self, staff_client):
        response = staff_client.get("/admin/api/waha-logout/")
        assert response.status_code == 405

    def test_requires_staff(self, non_staff_client):
        response = non_staff_client.post("/admin/api/waha-logout/")
        assert response.status_code == 302
