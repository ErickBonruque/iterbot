from unittest.mock import MagicMock

from django.test import TestCase

from apps.bot.models import ConversationState
from apps.bot.services import BotService
from apps.courses.models import Course
from apps.users.models import UserProfile


class JobSearchHandlerTests(TestCase):
    def setUp(self):
        self.waha_client = MagicMock()
        self.waha_client.settings = MagicMock(session_name="test-session")
        self.service = BotService(waha_client=self.waha_client)

    def _authenticate_user(self, chat_id: str) -> UserProfile:
        user = UserProfile.objects.create(phone_number=chat_id, is_authenticated_utfpr=True)
        ConversationState.objects.get_or_create(user=user)
        return user

    def test_authenticated_user_option_2_enters_job_search_flow(self):
        chat_id = "5522111111111@c.us"
        self._authenticate_user(chat_id)
        self.service.process_message(chat_id, "3", from_me=False)
        self.assertTrue(self.waha_client.send_message.called)

    def test_unauthenticated_user_option_3_prompts_authentication(self):
        chat_id = "5522222222222@c.us"
        self.service.process_message(chat_id, "3", from_me=False)
        self.assertTrue(self.waha_client.send_message.called)

    def test_from_me_true_does_not_process(self):
        chat_id = "5522333333333@c.us"
        self._authenticate_user(chat_id)
        self.service.process_message(chat_id, "3", from_me=True)
        self.assertFalse(self.waha_client.send_message.called)


class JobSearchHandlerCourseSelectionTests(TestCase):
    """Testes para o fluxo de seleção de curso e busca de vagas."""

    def setUp(self):
        self.waha_client = MagicMock()
        self.waha_client.settings = MagicMock(session_name="test-session")
        self.job_service = MagicMock()
        self.service = BotService(waha_client=self.waha_client, job_service=self.job_service)

    def _authenticate_user(self, chat_id: str) -> UserProfile:
        user = UserProfile.objects.create(phone_number=chat_id, is_authenticated_utfpr=True)
        ConversationState.objects.get_or_create(user=user)
        return user

    def test_no_courses_available_sends_message(self):
        """Sem cursos cadastrados, deve enviar mensagem de aviso."""
        chat_id = "5522444444444@c.us"
        self._authenticate_user(chat_id)
        Course.objects.all().delete()
        self.service.process_message(chat_id, "3", from_me=False)
        self.assertTrue(self.waha_client.send_message.called)

    def test_unauthenticated_user_option_3_sends_login_prompt(self):
        """Usuário não autenticado na opção 3 deve receber pedido para se cadastrar."""
        chat_id = "5522555555555@c.us"
        self.service.process_message(chat_id, "3", from_me=False)
        sent_text = self.waha_client.send_message.call_args[0][1]
        self.assertIn("cadastrar", sent_text.lower())

    def test_course_selection_with_invalid_number_sends_error(self):
        """Seleção de curso com número inválido deve exibir mensagem de erro."""
        chat_id = "5522666666666@c.us"
        user = UserProfile.objects.create(phone_number=chat_id, is_authenticated_utfpr=True)
        state, _ = ConversationState.objects.get_or_create(user=user)
        state.current_action = "course_selection"
        state.save(update_fields=["current_action", "updated_at"])
        self.service.process_message(chat_id, "abc", from_me=False)
        self.assertTrue(self.waha_client.send_message.called)
