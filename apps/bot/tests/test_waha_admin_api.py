"""Testes para endpoints admin WAHA — /admin/api/waha-status/ e /admin/api/waha-restart/.

WAHA-03: card de status em tempo real e botão de reconexão manual.
"""

import pytest
from django.contrib.auth import get_user_model
from django.test import Client


@pytest.fixture
def staff_client(db):
    """Client autenticado como staff."""
    User = get_user_model()
    user = User.objects.create_user(
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
    User = get_user_model()
    user = User.objects.create_user(
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
