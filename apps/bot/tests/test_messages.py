from unittest.mock import MagicMock

from django.test import TestCase

from apps.bot.handlers.base import BaseHandler
from apps.bot.messages import BOT_MESSAGES, MessageTemplate
from apps.bot.models import BotMessage


class _DummyHandler(BaseHandler):
    def handle(self, user, chat_id: str, text: str) -> bool:  # pragma: no cover - stub
        return False


class BotMessagesCatalogTests(TestCase):
    def test_catalog_exposes_required_namespaces(self):
        self.assertTrue(hasattr(BOT_MESSAGES, "auth"))
        self.assertTrue(hasattr(BOT_MESSAGES, "menu"))
        self.assertTrue(hasattr(BOT_MESSAGES, "search"))
        self.assertTrue(hasattr(BOT_MESSAGES, "review"))

    def test_dynamic_templates_use_named_placeholders(self):
        waiting = BOT_MESSAGES.auth.login_waiting_confirmation
        self.assertIsInstance(waiting, MessageTemplate)
        self.assertIn("{email}", waiting.text)

        menu = BOT_MESSAGES.menu.main_authenticated
        rendered = menu.text.format(
            brand_header=BOT_MESSAGES.menu.brand_header,
            ra="a1234567",
        )
        self.assertIn("a1234567", rendered)


class MessageResolutionTests(TestCase):
    def setUp(self):
        self.waha_client = MagicMock()
        self.waha_client.settings = MagicMock(session_name="test")
        self.handler = _DummyHandler(self.waha_client)

    def test_get_text_uses_db_override_when_available(self):
        BotMessage.objects.create(
            key=BOT_MESSAGES.auth.login_prompt_ra.key,
            text="Mensagem customizada",
            description="teste",
        )
        value = self.handler.get_text(BOT_MESSAGES.auth.login_prompt_ra.key, "default")
        self.assertEqual(value, "Mensagem customizada")

    def test_resolve_message_falls_back_to_default_with_formatting(self):
        value = self.handler.resolve_message(
            BOT_MESSAGES.menu.main_authenticated.key,
            BOT_MESSAGES.menu.main_authenticated.text,
            brand_header=BOT_MESSAGES.menu.brand_header,
            ra="a999999",
        )
        self.assertIn("a999999", value)
        self.assertIn("IterBot", value)

    def test_resolve_message_preserves_unknown_placeholder(self):
        value = self.handler.resolve_message(
            "auth.some_key",
            "Olá {name}, use {missing}",
            name="Maria",
        )
        self.assertIn("Maria", value)
        self.assertIn("{missing}", value)


class BotMessageKeyChoicesTests(TestCase):
    def test_key_choices_contains_domain_keys(self):
        keys = {choice[0] for choice in BotMessage.KEY_CHOICES}
        expected = {
            BOT_MESSAGES.auth.login_prompt_ra.key,
            BOT_MESSAGES.menu.main_authenticated.key,
            BOT_MESSAGES.search.selection_intro.key,
            BOT_MESSAGES.review.searching_review.key,
            "login_prompt_ra",  # compatibilidade legada
            "unknown_command",  # compatibilidade legada
        }
        self.assertTrue(expected.issubset(keys))
