import json
from unittest.mock import patch

from django.test import Client, TestCase, override_settings


class WebhookSecurityRedirectTests(TestCase):
    @override_settings(
        DEBUG=False,
        ALLOWED_HOSTS=["testserver"],
        SECURE_SSL_REDIRECT=True,
        SECURE_REDIRECT_EXEMPT=[],
    )
    @patch("apps.bot.views.BotService")
    def test_webhook_is_redirected_without_exempt_path(self, bot_service_cls):
        client = Client()
        payload = {
            "event": "message.any",
            "payload": {
                "body": "oi",
                "from": "5511999999999@c.us",
                "fromMe": False,
            },
        }

        response = client.post(
            "/webhook/",
            data=json.dumps(payload),
            content_type="application/json",
            secure=False,
        )

        self.assertEqual(response.status_code, 301)
        self.assertEqual(response["Location"], "https://testserver/webhook/")
        bot_service_cls.return_value.process_message.assert_not_called()

    @override_settings(
        DEBUG=False,
        ALLOWED_HOSTS=["testserver"],
        SECURE_SSL_REDIRECT=True,
        SECURE_REDIRECT_EXEMPT=[r"^webhook/$"],
    )
    @patch("apps.bot.views.BotService")
    def test_webhook_accepts_internal_http_when_exempted(self, bot_service_cls):
        client = Client()
        payload = {
            "event": "message.any",
            "payload": {
                "body": "oi",
                "from": "5511999999999@c.us",
                "fromMe": False,
            },
        }

        response = client.post(
            "/webhook/",
            data=json.dumps(payload),
            content_type="application/json",
            secure=False,
        )

        self.assertEqual(response.status_code, 200)
        bot_service_cls.return_value.process_message.assert_called_once_with(
            "5511999999999@c.us", "oi", False
        )
