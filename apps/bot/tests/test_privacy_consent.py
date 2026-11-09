"""Consentimento de privacidade (LGPD) no primeiro contato com o bot.

Regras:
- Quem ainda não aceitou recebe o texto de privacidade antes de qualquer coisa.
- O aceite só vale depois que o texto foi mostrado (estado `privacy_consent`).
- O aceite registra data/hora e um hash curto do texto exato que foi aceito.
- Quem recusa tem o perfil e a conversa apagados.
- O texto é editável no admin (BotMessage) como as outras mensagens.
- "parar"/"retomar" desligam/religam o resumo semanal.
"""

from unittest.mock import MagicMock

import pytest
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.bot.messages import BOT_MESSAGES
from apps.bot.models import BotMessage, ConversationState, InteractionLog
from apps.bot.services import BotService
from apps.users.models import UserProfile

CHAT_ID = "5545988887777@c.us"

pytestmark = pytest.mark.no_consent_default


class PrivacyConsentTests(TestCase):
    def setUp(self):
        self.waha_client = MagicMock()
        self.waha_client.settings = MagicMock(session_name="test-session")
        self.waha_client.send_message.return_value = True
        self.service = BotService(waha_client=self.waha_client)

    def _send(self, text: str) -> None:
        self.service.process_message(CHAT_ID, text, from_me=False)

    def _sent_texts(self) -> list[str]:
        return [c.args[1] for c in self.waha_client.send_message.call_args_list]

    def _last_sent(self) -> str:
        return self._sent_texts()[-1]

    def test_first_contact_shows_privacy_text_instead_of_menu(self):
        self._send("oi")

        self.assertIn("privacidade", self._last_sent().lower())
        self.assertFalse(any("Cadastro/Login de aluno" in t for t in self._sent_texts()))
        user = UserProfile.objects.get(phone_number=CHAT_ID)
        self.assertIsNone(user.privacy_consent_at)
        self.assertEqual(user.conversation_state.current_action, "privacy_consent")

    def test_option_one_before_seeing_the_text_does_not_count_as_consent(self):
        self._send("1")

        user = UserProfile.objects.get(phone_number=CHAT_ID)
        self.assertIsNone(user.privacy_consent_at)
        self.assertIn("privacidade", self._last_sent().lower())

    def test_accepting_records_timestamp_and_text_version_then_shows_menu(self):
        self._send("oi")
        self._send("1")

        user = UserProfile.objects.get(phone_number=CHAT_ID)
        self.assertIsNotNone(user.privacy_consent_at)
        self.assertRegex(user.privacy_consent_version, r"^[0-9a-f]{12}$")
        self.assertIn("Cadastro/Login de aluno", self._last_sent())
        self.assertIsNone(user.conversation_state.current_action)

    def test_accept_by_word(self):
        self._send("oi")
        self._send("Aceito")

        self.assertIsNotNone(UserProfile.objects.get(phone_number=CHAT_ID).privacy_consent_at)

    def test_other_text_while_pending_repeats_the_privacy_text(self):
        self._send("oi")
        self._send("quero vagas")

        user = UserProfile.objects.get(phone_number=CHAT_ID)
        self.assertIsNone(user.privacy_consent_at)
        self.assertIn("privacidade", self._last_sent().lower())

    def test_declining_deletes_profile_and_conversation(self):
        self._send("oi")
        self._send("2")

        self.assertFalse(UserProfile.objects.filter(phone_number=CHAT_ID).exists())
        self.assertFalse(InteractionLog.objects.filter(user__phone_number=CHAT_ID).exists())
        self.assertIn("não vou guardar", self._last_sent().lower())

    def test_user_who_declined_can_start_over(self):
        self._send("oi")
        self._send("2")
        self._send("oi")

        self.assertIn("privacidade", self._last_sent().lower())

    def test_consented_user_goes_straight_to_menu(self):
        UserProfile.objects.create(phone_number=CHAT_ID, privacy_consent_at=timezone.now())

        self._send("oi")

        self.assertEqual(len(self._sent_texts()), 1)
        self.assertIn("Cadastro/Login de aluno", self._last_sent())

    def test_existing_user_without_consent_is_asked_too(self):
        user = UserProfile.objects.create(phone_number=CHAT_ID, is_authenticated_utfpr=True)
        ConversationState.objects.get_or_create(user=user)

        self._send("oi")

        self.assertIn("privacidade", self._last_sent().lower())

    @override_settings(PRIVACY_CONTACT_EMAIL="lgpd@exemplo.utfpr.edu.br")
    def test_privacy_text_shows_contact_email(self):
        self._send("oi")

        self.assertIn("lgpd@exemplo.utfpr.edu.br", self._last_sent())

    def test_text_edited_in_admin_is_used_and_changes_the_version(self):
        self._send("oi")
        self._send("1")
        default_version = UserProfile.objects.get(phone_number=CHAT_ID).privacy_consent_version

        other = "5545911112222@c.us"
        BotMessage.objects.create(
            key=BOT_MESSAGES.auth.privacy_consent.key,
            text="🔒 Texto de privacidade revisado. 1 aceito, 2 não aceito.",
        )
        self.service.process_message(other, "oi", from_me=False)
        self.assertIn("revisado", self._last_sent())
        self.service.process_message(other, "1", from_me=False)

        edited_version = UserProfile.objects.get(phone_number=other).privacy_consent_version
        self.assertNotEqual(default_version, edited_version)


class WeeklyReviewOptOutTests(TestCase):
    def setUp(self):
        self.waha_client = MagicMock()
        self.waha_client.settings = MagicMock(session_name="test-session")
        self.service = BotService(waha_client=self.waha_client)
        self.user = UserProfile.objects.create(
            phone_number=CHAT_ID, privacy_consent_at=timezone.now()
        )

    def test_parar_turns_weekly_review_off_and_retomar_turns_it_back_on(self):
        self.service.process_message(CHAT_ID, "parar", from_me=False)
        self.user.refresh_from_db()
        self.assertTrue(self.user.weekly_review_opt_out)

        self.service.process_message(CHAT_ID, "retomar", from_me=False)
        self.user.refresh_from_db()
        self.assertFalse(self.user.weekly_review_opt_out)
