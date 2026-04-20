import json
from unittest.mock import patch

from django.test import Client, TestCase


class WebhookViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.valid_payload = {
            "event": "message.any",
            "payload": {
                "body": "oi",
                "from": "5511999999999@c.us",
                "fromMe": False,
            },
        }

    @patch("apps.bot.views.BotService")
    def test_valid_message_calls_process_and_returns_200(self, mock_bot_service):
        response = self.client.post(
            "/webhook/",
            data=json.dumps(self.valid_payload),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        mock_bot_service.return_value.process_message.assert_called_once_with(
            "5511999999999@c.us", "oi", False
        )

    @patch("apps.bot.views.BotService")
    def test_from_me_is_ignored_with_200(self, mock_bot_service):
        payload = dict(self.valid_payload)
        payload["payload"] = dict(payload["payload"])
        payload["payload"]["fromMe"] = True

        response = self.client.post(
            "/webhook/",
            data=json.dumps(payload),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        mock_bot_service.return_value.process_message.assert_not_called()

    def test_invalid_json_returns_400(self):
        response = self.client.post(
            "/webhook/",
            data="INVALID_JSON_DATA",
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)

    def test_invalid_event_returns_400(self):
        payload = {
            "event": "session.status",
            "payload": {"body": "oi", "from": "5511999999999@c.us", "fromMe": False},
        }

        response = self.client.post(
            "/webhook/",
            data=json.dumps(payload),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)

    def test_missing_body_returns_400(self):
        payload = {
            "event": "message.any",
            "payload": {"body": "", "from": "5511999999999@c.us", "fromMe": False},
        }

        response = self.client.post(
            "/webhook/",
            data=json.dumps(payload),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)

    @patch("apps.bot.views.BotService")
    def test_internal_error_returns_500(self, mock_bot_service):
        mock_bot_service.return_value.process_message.side_effect = RuntimeError("boom")

        response = self.client.post(
            "/webhook/",
            data=json.dumps(self.valid_payload),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 500)

    def test_get_request_returns_405(self):
        response = self.client.get("/webhook/")
        self.assertEqual(response.status_code, 405)
