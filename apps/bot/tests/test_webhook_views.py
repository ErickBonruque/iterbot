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
    def test_post_valid_message_returns_200(self, mock_bot_service):  # - mock convention
        mock_bot_service.return_value.process_message.return_value = None
        response = self.client.post(
            "/webhook/",
            data=json.dumps(self.valid_payload),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)

    @patch("apps.bot.views.BotService")
    def test_post_from_me_true_does_not_call_process_message(self, mock_bot_service):
        payload = dict(self.valid_payload)
        payload["payload"] = dict(payload["payload"])
        payload["payload"]["fromMe"] = True
        self.client.post(
            "/webhook/",
            data=json.dumps(payload),
            content_type="application/json",
        )
        mock_bot_service.return_value.process_message.assert_not_called()

    def test_get_request_returns_405(self):
        response = self.client.get("/webhook/")
        self.assertEqual(response.status_code, 405)


class WebhookViewEventFilterTests(TestCase):
    """Testes para filtragem de eventos no webhook."""

    def setUp(self):
        self.client = Client()

    @patch("apps.bot.views.BotService")
    def test_post_non_message_event_does_not_call_process_message(self, mock_bot_service):
        """Evento que não contém 'message' não deve chamar BotService.process_message."""
        payload = {
            "event": "session.status",
            "payload": {
                "body": "oi",
                "from": "5511999999999@c.us",
                "fromMe": False,
            },
        }
        response = self.client.post(
            "/webhook/",
            data=json.dumps(payload),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        mock_bot_service.return_value.process_message.assert_not_called()

    def test_post_invalid_json_returns_error(self):
        """Requisição com body inválido (não-JSON) deve retornar status de erro."""
        response = self.client.post(
            "/webhook/",
            data="INVALID_JSON_DATA",
            content_type="application/json",
        )
        self.assertNotEqual(response.status_code, 200)

    @patch("apps.bot.views.BotService")
    def test_post_empty_body_does_not_call_process_message(self, mock_bot_service):
        """Mensagem com body vazio não deve chamar BotService.process_message."""
        payload = {
            "event": "message.any",
            "payload": {
                "body": "",
                "from": "5511999999999@c.us",
                "fromMe": False,
            },
        }
        response = self.client.post(
            "/webhook/",
            data=json.dumps(payload),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        mock_bot_service.return_value.process_message.assert_not_called()
