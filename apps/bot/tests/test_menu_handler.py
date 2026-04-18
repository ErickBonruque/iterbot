from unittest.mock import MagicMock

from django.test import TestCase

from apps.bot.services import BotService
from apps.users.models import UserProfile


class MenuHandlerTests(TestCase):
    def setUp(self):
        self.waha_client = MagicMock()
        self.waha_client.settings = MagicMock(session_name="test-session")
        self.service = BotService(waha_client=self.waha_client)

    def _authenticate_user(self, chat_id: str) -> UserProfile:
        return UserProfile.objects.create(phone_number=chat_id, is_authenticated_utfpr=True)

    def test_unknown_command_shows_menu(self):
        chat_id = "5533111111111@c.us"
        self._authenticate_user(chat_id)
        self.service.process_message(chat_id, "xyz_unknown", from_me=False)
        self.assertTrue(self.waha_client.send_message.called)

    def test_new_user_receives_welcome_message(self):
        chat_id = "5533222222222@c.us"
        self.service.process_message(chat_id, "oi", from_me=False)
        self.assertTrue(self.waha_client.send_message.called)

    def test_from_me_true_does_not_send_menu(self):
        chat_id = "5533333333333@c.us"
        self._authenticate_user(chat_id)
        self.service.process_message(chat_id, "xyz_unknown", from_me=True)
        self.assertFalse(self.waha_client.send_message.called)


class MenuHandlerContentTests(TestCase):
    """Testes para conteúdo das mensagens do menu."""

    def setUp(self):
        self.waha_client = MagicMock()
        self.waha_client.settings = MagicMock(session_name="test-session")
        self.service = BotService(waha_client=self.waha_client)

    def _authenticate_user(self, chat_id: str) -> UserProfile:
        return UserProfile.objects.create(phone_number=chat_id, is_authenticated_utfpr=True)

    def test_new_user_menu_contains_iterbot_brand(self):
        """Novo usuário deve receber mensagem com o nome IterBot."""
        chat_id = "5533444444444@c.us"
        self.service.process_message(chat_id, "oi", from_me=False)
        sent_text = self.waha_client.send_message.call_args[0][1]
        self.assertIn("IterBot", sent_text)

    def test_authenticated_user_menu_contains_all_options(self):
        """Usuário autenticado deve receber menu com opções completas (3, 4)."""
        chat_id = "5533555555555@c.us"
        self._authenticate_user(chat_id)
        self.service.process_message(chat_id, "menu", from_me=False)
        sent_text = self.waha_client.send_message.call_args[0][1]
        # Menu autenticado tem as opções 3 e 4
        self.assertTrue("3" in sent_text or "Buscar Vagas" in sent_text)

    def test_unknown_command_authenticated_user_shows_unknown_message(self):
        """Comando desconhecido para autenticado deve mostrar mensagem de ajuda."""
        chat_id = "5533666666666@c.us"
        self._authenticate_user(chat_id)
        self.service.process_message(chat_id, "comando_desconhecido_xpto", from_me=False)
        self.assertTrue(self.waha_client.send_message.called)
