"""Senhas digitadas no WhatsApp não podem ir em texto puro para o InteractionLog.

O login de empresa pelo bot pede a senha do portal; o `process_message` grava
toda mensagem recebida no `InteractionLog` (pesquisável no admin). No passo de
senha o conteúdo tem de ser substituído por um marcador.
"""

from unittest.mock import MagicMock

from django.test import TestCase

from apps.bot.models import ConversationState, InteractionLog
from apps.bot.services import SENSITIVE_INPUT_PLACEHOLDER, BotService
from apps.users.models import UserProfile


class SensitiveInputLoggingTests(TestCase):
    def setUp(self):
        self.waha_client = MagicMock()
        self.waha_client.settings = MagicMock(session_name="test-session")
        self.service = BotService(waha_client=self.waha_client)
        self.chat_id = "5545999990000@c.us"
        self.user = UserProfile.objects.create(phone_number=self.chat_id)

    def _set_state(self, action: str, flow_data: dict) -> None:
        state, _ = ConversationState.objects.get_or_create(user=self.user)
        state.current_action = action
        state.flow_data = flow_data
        state.save(update_fields=["current_action", "flow_data", "updated_at"])

    def _received_contents(self) -> list[str]:
        return list(
            InteractionLog.objects.filter(user=self.user, message_type="RECEIVED").values_list(
                "message_content", flat=True
            )
        )

    def test_company_password_is_not_logged_in_plain_text(self):
        self._set_state("company_login_password", {"company_email": "rh@empresa.com"})

        self.service.process_message(self.chat_id, "MinhaSenhaSecreta!9", from_me=False)

        contents = self._received_contents()
        self.assertEqual(contents, [SENSITIVE_INPUT_PLACEHOLDER])

    def test_regular_messages_are_still_logged(self):
        self.service.process_message(self.chat_id, "oi", from_me=False)

        self.assertEqual(self._received_contents(), ["oi"])
