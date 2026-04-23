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
    @patch("apps.bot.tasks.process_webhook_message.delay")
    def test_webhook_is_redirected_without_exempt_path(self, mock_delay):
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
        mock_delay.assert_not_called()

    @override_settings(
        DEBUG=False,
        ALLOWED_HOSTS=["testserver"],
        SECURE_SSL_REDIRECT=True,
        SECURE_REDIRECT_EXEMPT=[r"^webhook/$"],
    )
    @patch("apps.bot.tasks.process_webhook_message.delay")
    def test_webhook_accepts_internal_http_when_exempted(self, mock_delay):
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
        mock_delay.assert_called_once_with("5511999999999@c.us", "oi")
