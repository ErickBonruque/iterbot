from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.bot.models import BotConfiguration
from config.env import settings


class BotConfigurationApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        user_model = get_user_model()
        self.admin = user_model.objects.create_superuser(
            username="testadmin",
            email="testadmin@example.com",
            password="testpass123",
        )
        self.client.force_authenticate(user=self.admin)

    def test_active_endpoint_returns_defaults(self):
        response = self.client.get("/api/bot/configuration/active/")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["waha_url"], settings.waha.base_url)
        self.assertEqual(payload["waha_api_key"], settings.waha.api_key)
        self.assertEqual(payload["waha_session"], settings.waha.session_name)
        self.assertEqual(payload["dashboard_username"], settings.dashboard_credentials.username)
        self.assertEqual(payload["admin_username"], settings.admin_credentials.username)

    def test_create_replaces_previous_configuration(self):
        BotConfiguration.objects.create(
            waha_url="http://old",
            waha_api_key="old",
            waha_session="old",
            dashboard_username="old",
            dashboard_password="old",
        )

        response = self.client.post(
            "/api/bot/configuration/",
            {
                "waha_url": "http://new",
                "waha_api_key": "new-key",
                "waha_session": "new-session",
                "dashboard_username": "new-user",
                "dashboard_password": "new-pass",
                "admin_username": "super",
                "admin_password": "super-pass",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(BotConfiguration.objects.count(), 1)
        active = BotConfiguration.objects.first()
        self.assertEqual(active.waha_url, "http://new")
        self.assertEqual(active.waha_api_key, "new-key")
        self.assertEqual(active.waha_session, "new-session")
        self.assertEqual(active.dashboard_username, "new-user")
        self.assertEqual(active.admin_username, "super")

    def test_create_syncs_django_admin_user(self):
        response = self.client.post(
            "/api/bot/configuration/",
            {
                "waha_url": "http://new",
                "waha_api_key": "new-key",
                "waha_session": "new-session",
                "dashboard_username": "new-user",
                "dashboard_password": "new-pass",
                "admin_username": "super",
                "admin_password": "super-pass",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        user_model = get_user_model()
        admin = user_model.objects.get(username="super")
        self.assertTrue(admin.is_staff)
        self.assertTrue(admin.is_superuser)
        self.assertTrue(admin.check_password("super-pass"))

    def test_unauthenticated_request_returns_403(self):
        """Endpoint deve rejeitar requisições sem autenticação."""
        unauthenticated_client = APIClient()
        response = unauthenticated_client.get("/api/bot/configuration/active/")
        self.assertIn(response.status_code, [401, 403])
