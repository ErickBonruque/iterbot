import json
import time
from unittest.mock import patch

from django.core.cache import cache
from django.test import Client, TestCase


class WebhookViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        cache.clear()
        self.valid_payload = {
            "event": "message.any",
            "payload": {
                "id": "false_5511999999999@c.us_3EB0AAAA",
                "body": "oi",
                "from": "5511999999999@c.us",
                "fromMe": False,
                "timestamp": int(time.time()),
            },
        }

    def _post(self, payload):
        return self.client.post(
            "/webhook/",
            data=json.dumps(payload),
            content_type="application/json",
        )

    @patch("apps.bot.tasks.process_webhook_message.delay")
    def test_valid_message_enqueues_task_and_returns_200(self, mock_delay):
        response = self.client.post(
            "/webhook/",
            data=json.dumps(self.valid_payload),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        mock_delay.assert_called_once_with("5511999999999@c.us", "oi")

    @patch("apps.bot.tasks.process_webhook_message.delay")
    def test_from_me_is_ignored_with_200(self, mock_delay):
        payload = dict(self.valid_payload)
        payload["payload"] = dict(payload["payload"])
        payload["payload"]["fromMe"] = True

        response = self.client.post(
            "/webhook/",
            data=json.dumps(payload),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        mock_delay.assert_not_called()

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

    def test_get_request_returns_405(self):
        response = self.client.get("/webhook/")
        self.assertEqual(response.status_code, 405)


class WebhookDeduplicationTests(TestCase):
    """O WAHA reentrega o mesmo evento em timeout/erro ou com hooks duplicados."""

    def setUp(self):
        self.client = Client()
        cache.clear()
        self.payload = {
            "event": "message.any",
            "payload": {
                "id": "false_5511999999999@c.us_3EB0AAAA",
                "body": "2",
                "from": "5511999999999@c.us",
                "fromMe": False,
                "timestamp": int(time.time()),
            },
        }

    def _post(self, payload):
        return self.client.post(
            "/webhook/",
            data=json.dumps(payload),
            content_type="application/json",
        )

    @patch("apps.bot.tasks.process_webhook_message.delay")
    def test_same_message_id_is_enqueued_only_once(self, mock_delay):
        first = self._post(self.payload)
        second = self._post(self.payload)

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        mock_delay.assert_called_once_with("5511999999999@c.us", "2")

    @patch("apps.bot.tasks.process_webhook_message.delay")
    def test_dedupe_falls_back_to_content_hash_without_id(self, mock_delay):
        payload = json.loads(json.dumps(self.payload))
        del payload["payload"]["id"]

        self._post(payload)
        self._post(payload)

        mock_delay.assert_called_once()

    @patch("apps.bot.tasks.process_webhook_message.delay")
    def test_different_messages_are_both_enqueued(self, mock_delay):
        other = json.loads(json.dumps(self.payload))
        other["payload"]["id"] = "false_5511999999999@c.us_3EB0BBBB"
        other["payload"]["body"] = "1"

        self._post(self.payload)
        self._post(other)

        self.assertEqual(mock_delay.call_count, 2)

    @patch("apps.bot.tasks.process_webhook_message.delay")
    def test_ack_event_is_ignored_with_200(self, mock_delay):
        payload = {
            "event": "message.ack",
            "payload": {"id": "x", "from": "5511999999999@c.us", "ack": 2},
        }

        response = self._post(payload)

        self.assertEqual(response.status_code, 200)
        mock_delay.assert_not_called()

    @patch("apps.bot.tasks.process_webhook_message.delay")
    def test_old_message_from_offline_backlog_is_discarded(self, mock_delay):
        payload = json.loads(json.dumps(self.payload))
        payload["payload"]["timestamp"] = int(time.time()) - 3600

        response = self._post(payload)

        self.assertEqual(response.status_code, 200)
        mock_delay.assert_not_called()

    @patch("apps.bot.tasks.process_webhook_message.delay")
    def test_millisecond_timestamp_is_accepted_as_recent(self, mock_delay):
        payload = json.loads(json.dumps(self.payload))
        payload["payload"]["timestamp"] = int(time.time() * 1000)

        self._post(payload)

        mock_delay.assert_called_once()
