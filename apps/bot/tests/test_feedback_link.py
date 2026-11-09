"""Comando 'opinião': manda o link do formulário de opinião do teste com alunos."""

from unittest.mock import MagicMock

from django.test import TestCase, override_settings

from apps.bot.services import BotService
from apps.users.models import UserProfile

CHAT_ID = "5545977776666@c.us"


class FeedbackLinkTests(TestCase):
    def setUp(self):
        self.waha_client = MagicMock()
        self.waha_client.settings = MagicMock(session_name="test-session")
        self.service = BotService(waha_client=self.waha_client)
        UserProfile.objects.create(phone_number=CHAT_ID)

    def _reply_to(self, text: str) -> str:
        self.service.process_message(CHAT_ID, text, from_me=False)
        return self.waha_client.send_message.call_args[0][1]

    @override_settings(FEEDBACK_FORM_URL="https://forms.gle/abc123")
    def test_opiniao_sends_the_form_link(self):
        for word in ("opinião", "opiniao", "feedback"):
            with self.subTest(word=word):
                self.assertIn("https://forms.gle/abc123", self._reply_to(word))

    @override_settings(FEEDBACK_FORM_URL="")
    def test_without_url_says_it_is_not_available(self):
        reply = self._reply_to("opinião")
        self.assertNotIn("{feedback_url}", reply)
        self.assertIn("ainda não", reply.lower())
