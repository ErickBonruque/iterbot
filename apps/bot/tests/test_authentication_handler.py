from unittest.mock import MagicMock, patch

from django.test import TestCase

from apps.bot.models import ConversationState

from apps.bot.services import BotService
from apps.users.models import UserProfile


class AuthenticationHandlerStartLoginTests(TestCase):
    def setUp(self):
        self.waha_client = MagicMock()
        self.waha_client.settings = MagicMock(session_name="test-session")
        self.service = BotService(waha_client=self.waha_client)

    def _authenticate_user(self, chat_id: str) -> UserProfile:
        user = UserProfile.objects.create(
            phone_number=chat_id, is_authenticated_utfpr=True
        )
        ConversationState.objects.get_or_create(user=user)
        return user

    def test_unauthenticated_user_option_1_enters_login_step_ra(self):
        chat_id = "5511111111111@c.us"
        self.service.process_message(chat_id, "1", from_me=False)
        user = UserProfile.objects.get(phone_number=chat_id)
        self.assertEqual(user.conversation_state.current_action, "login_step_ra")

    def test_already_authenticated_user_option_1_shows_already_registered(self):
        chat_id = "5511222222222@c.us"
        self._authenticate_user(chat_id)
        self.service.process_message(chat_id, "1", from_me=False)
        sent_text = self.waha_client.send_message.call_args[0][1]
        self.assertIn("já está cadastrado", sent_text.lower())

    def test_login_step_ra_too_short_asks_again(self):
        chat_id = "5511333333333@c.us"
        user = UserProfile.objects.create(phone_number=chat_id)
        state, _ = ConversationState.objects.get_or_create(user=user)
        state.current_action = "login_step_ra"
        state.save(update_fields=["current_action", "updated_at"])
        self.service.process_message(chat_id, "ab", from_me=False)
        self.assertTrue(self.waha_client.send_message.called)

    def test_from_me_true_does_not_process(self):
        chat_id = "5511444444444@c.us"
        self.service.process_message(chat_id, "1", from_me=True)
        self.assertFalse(self.waha_client.send_message.called)


class AuthenticationHandlerLoginStepRaTests(TestCase):
    """Testes para o fluxo de login no step de RA."""

    def setUp(self):
        self.waha_client = MagicMock()
        self.waha_client.settings = MagicMock(session_name="test-session")
        self.service = BotService(waha_client=self.waha_client)

    def test_valid_ra_advances_to_password_step(self):
        """RA com comprimento válido (≥5) deve avançar para login_step_password."""
        chat_id = "5511555555555@c.us"
        user = UserProfile.objects.create(phone_number=chat_id)
        state, _ = ConversationState.objects.get_or_create(user=user)
        state.current_action = "login_step_ra"
        state.save(update_fields=["current_action", "updated_at"])
        self.service.process_message(chat_id, "a1234", from_me=False)
        user = UserProfile.objects.get(phone_number=chat_id)
        self.assertEqual(user.conversation_state.current_action, "login_step_password")

    def test_ra_too_short_keeps_login_step_ra(self):
        """RA com menos de 5 caracteres deve manter current_action como login_step_ra."""
        chat_id = "5511666666666@c.us"
        user = UserProfile.objects.create(phone_number=chat_id)
        state, _ = ConversationState.objects.get_or_create(user=user)
        state.current_action = "login_step_ra"
        state.save(update_fields=["current_action", "updated_at"])
        self.service.process_message(chat_id, "ab", from_me=False)
        user = UserProfile.objects.get(phone_number=chat_id)
        self.assertEqual(user.conversation_state.current_action, "login_step_ra")


class AuthenticationHandlerLoginPasswordTests(TestCase):
    """Testes para o fluxo de login no step de Senha."""

    def setUp(self):
        self.waha_client = MagicMock()
        self.waha_client.settings = MagicMock(session_name="test-session")
        self.service = BotService(waha_client=self.waha_client)

    @patch("apps.users.services.UTFPRAuthService.authenticate")
    def test_valid_password_sends_message(self, mock_authenticate):
        """Senha com RA em flow_data deve enviar mensagem (validação em progresso)."""
        mock_authenticate.return_value = True

        chat_id = "5511777777777@c.us"
        user = UserProfile.objects.create(phone_number=chat_id)
        state, _ = ConversationState.objects.get_or_create(user=user)
        state.current_action = "login_step_password"
        state.flow_data = {"temp_ra": "12345"}
        state.save(update_fields=["current_action", "flow_data", "updated_at"])
        self.service.process_message(chat_id, "senha123", from_me=False)
        # Deve ter enviado mensagem (validando/avançando ou erro)
        self.assertTrue(self.waha_client.send_message.called)

    def test_password_step_without_temp_ra_sends_error(self):
        """Step de senha sem RA no flow_data deve enviar mensagem de erro de fluxo."""
        chat_id = "5511888888888@c.us"
        user = UserProfile.objects.create(phone_number=chat_id)
        state, _ = ConversationState.objects.get_or_create(user=user)
        state.current_action = "login_step_password"
        state.flow_data = {}  # sem temp_ra
        state.save(update_fields=["current_action", "flow_data", "updated_at"])
        self.service.process_message(chat_id, "senha_qualquer", from_me=False)
        self.assertTrue(self.waha_client.send_message.called)
