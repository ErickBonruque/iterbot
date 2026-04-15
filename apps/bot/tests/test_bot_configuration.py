from django.test import TestCase

from apps.bot.models import BotConfiguration
from apps.bot.services import BotService


class BotConfigurationTests(TestCase):
    def test_get_active_returns_runtime_waha_settings(self):
        BotConfiguration.objects.create(
            waha_url="http://custom-waha:3000",
            waha_api_key="custom-key",
            waha_session="custom-session",
        )

        settings = BotConfiguration.get_active()

        self.assertEqual(settings.base_url, "http://custom-waha:3000")
        self.assertEqual(settings.api_key, "custom-key")
        self.assertEqual(settings.session_name, "custom-session")

    def test_bot_service_initializes_when_configuration_exists(self):
        BotConfiguration.objects.create(
            waha_url="http://custom-waha:3000",
            waha_api_key="custom-key",
            waha_session="custom-session",
        )

        service = BotService()

        self.assertEqual(service.waha_client.settings.base_url, "http://custom-waha:3000")
        self.assertEqual(service.waha_client.settings.api_key, "custom-key")
        self.assertEqual(service.waha_client.settings.session_name, "custom-session")
