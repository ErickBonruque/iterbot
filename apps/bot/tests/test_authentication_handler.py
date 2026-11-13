from unittest.mock import MagicMock

from django.test import TestCase, override_settings

from apps.bot.models import ConversationState
from apps.bot.services import BotService
from apps.users.models import UserProfile


class AuthenticationHandlerStartLoginTests(TestCase):
    def setUp(self):
        self.waha_client = MagicMock()
        self.waha_client.settings = MagicMock(session_name="test-session")
        self.service = BotService(waha_client=self.waha_client)

    def _authenticate_user(self, chat_id: str) -> UserProfile:
        user = UserProfile.objects.create(phone_number=chat_id, is_authenticated_utfpr=True)
        ConversationState.objects.get_or_create(user=user)
        return user

    def test_unauthenticated_user_option_1_enters_login_step_ra(self):
        chat_id = "5511111111111@c.us"
        self.service.process_message(chat_id, "1", from_me=False)
        user = UserProfile.objects.get(phone_number=chat_id)
        self.assertEqual(user.conversation_state.current_action, "login_step_ra")

    def test_authenticated_user_register_alias_shows_already_registered(self):
        """O alias textual 'cadastrar' (e 'login'/'entrar') ainda ativa o gate
        de 'já cadastrado' no start_login_flow para usuário autenticado.

        Observação: a opção numérica '1' no menu autenticado agora é Buscar
        Vagas (não cadastro), mas as palavras-chave continuam roteando para
        start_login_flow para preservar UX de usuários que digitarem por nome.
        """
        chat_id = "5511222222222@c.us"
        self._authenticate_user(chat_id)
        self.service.process_message(chat_id, "cadastrar", from_me=False)
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

    def test_valid_ra_advances_straight_to_email_step(self):
        """RA válido (≥5) vai direto para o e-mail: o bot não pede mais senha."""
        chat_id = "5511555555555@c.us"
        user = UserProfile.objects.create(phone_number=chat_id)
        state, _ = ConversationState.objects.get_or_create(user=user)
        state.current_action = "login_step_ra"
        state.save(update_fields=["current_action", "updated_at"])
        self.service.process_message(chat_id, "a1234567", from_me=False)
        user = UserProfile.objects.get(phone_number=chat_id)
        self.assertEqual(user.conversation_state.current_action, "login_step_email")
        self.assertEqual(user.conversation_state.flow_data.get("temp_ra"), "a1234567")
        sent_texts = [c.args[1] for c in self.waha_client.send_message.call_args_list]
        self.assertIn("e-mail institucional", sent_texts[-1].lower())
        self.assertFalse(any("senha" in t.lower() for t in sent_texts))

    def test_verified_user_relogs_at_ra_step_without_email(self):
        """Re-login: perfil com e-mail já verificado é autenticado logo após o RA.

        Regressão do bug em que, após logout, o bot pedia o e-mail de novo
        mesmo com o perfil já confirmado.
        """
        chat_id = "5511666666666@c.us"
        user = UserProfile.objects.create(
            phone_number=chat_id,
            ra="a1234567",
            email="aluno@alunos.utfpr.edu.br",
            email_verified=True,
            is_authenticated_utfpr=False,
        )
        state, _ = ConversationState.objects.get_or_create(user=user)
        state.current_action = "login_step_ra"
        state.save(update_fields=["current_action", "updated_at"])

        self.service.process_message(chat_id, "a1234567", from_me=False)

        user.refresh_from_db()
        self.assertTrue(user.is_authenticated_utfpr)
        self.assertIsNone(user.conversation_state.current_action)
        sent_texts = [c.args[1] for c in self.waha_client.send_message.call_args_list]
        self.assertFalse(any("e-mail institucional" in t.lower() for t in sent_texts))

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


class AuthenticationHandlerLoginEmailTests(TestCase):
    """Passo de e-mail: vincula RA + e-mail e dispara a confirmação por link."""

    def setUp(self):
        self.waha_client = MagicMock()
        self.waha_client.settings = MagicMock(session_name="test-session")
        self.dispatcher = MagicMock()
        self.service = BotService(waha_client=self.waha_client, email_dispatcher=self.dispatcher)

    def _user_in_state(self, chat_id: str, action: str, flow_data: dict) -> UserProfile:
        user = UserProfile.objects.create(phone_number=chat_id)
        state, _ = ConversationState.objects.get_or_create(user=user)
        state.current_action = action
        state.flow_data = flow_data
        state.save(update_fields=["current_action", "flow_data", "updated_at"])
        return user

    def test_email_step_links_ra_and_dispatches_confirmation(self):
        chat_id = "5511777777777@c.us"
        user = self._user_in_state(chat_id, "login_step_email", {"temp_ra": "a1234567"})

        self.service.process_message(chat_id, "aluno@alunos.utfpr.edu.br", from_me=False)

        user.refresh_from_db()
        self.assertEqual(user.ra, "a1234567")
        self.assertEqual(user.email, "aluno@alunos.utfpr.edu.br")
        self.assertFalse(user.email_verified)
        self.assertEqual(user.conversation_state.current_action, "login_step_waiting_confirmation")
        self.dispatcher.dispatch_confirmation_email.assert_called_once_with(user.id)

    @override_settings(STUDENT_TEST_EMAILS=frozenset({"iterbot.teste01@alunos.utfpr.edu.br"}))
    def test_test_email_authenticates_without_sending_link(self):
        chat_id = "5511777777770@c.us"
        user = self._user_in_state(chat_id, "login_step_email", {"temp_ra": "a1234567"})

        self.service.process_message(chat_id, "iterbot.teste01@alunos.utfpr.edu.br", from_me=False)

        user.refresh_from_db()
        self.assertTrue(user.email_verified)
        self.assertTrue(user.is_authenticated_utfpr)
        self.assertIsNone(user.conversation_state.current_action)
        self.dispatcher.dispatch_confirmation_email.assert_not_called()
        sent_text = self.waha_client.send_message.call_args[0][1]
        self.assertIn("Conta de teste", sent_text)

    def test_email_already_linked_to_other_number_asks_another(self):
        UserProfile.objects.create(
            phone_number="5511000000000@c.us", email="aluno@alunos.utfpr.edu.br"
        )
        chat_id = "5511777777771@c.us"
        user = self._user_in_state(chat_id, "login_step_email", {"temp_ra": "a1234567"})

        self.service.process_message(chat_id, "aluno@alunos.utfpr.edu.br", from_me=False)

        user.refresh_from_db()
        self.assertIsNone(user.email)
        self.assertEqual(user.conversation_state.current_action, "login_step_email")
        self.dispatcher.dispatch_confirmation_email.assert_not_called()
        sent_text = self.waha_client.send_message.call_args[0][1]
        self.assertIn("outro número", sent_text)

    def test_email_step_without_temp_ra_sends_flow_error(self):
        chat_id = "5511888888888@c.us"
        user = self._user_in_state(chat_id, "login_step_email", {})

        self.service.process_message(chat_id, "aluno@alunos.utfpr.edu.br", from_me=False)

        user.refresh_from_db()
        self.assertIsNone(user.conversation_state.current_action)
        self.dispatcher.dispatch_confirmation_email.assert_not_called()

    def test_legacy_password_state_is_handled_as_email_step(self):
        """Quem ficou parado no antigo passo de senha recebe o pedido de e-mail.

        O texto que a pessoa digitar é tratado como e-mail (inválido se for uma
        senha) — nunca é guardado como senha.
        """
        chat_id = "5511999888777@c.us"
        user = self._user_in_state(chat_id, "login_step_password", {"temp_ra": "a1234567"})

        self.service.process_message(chat_id, "aluno@alunos.utfpr.edu.br", from_me=False)

        user.refresh_from_db()
        self.assertEqual(user.conversation_state.current_action, "login_step_waiting_confirmation")
        self.dispatcher.dispatch_confirmation_email.assert_called_once_with(user.id)
