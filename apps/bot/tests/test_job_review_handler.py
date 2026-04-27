from unittest.mock import MagicMock, patch

from django.test import TestCase

from apps.bot.models import ConversationState
from apps.bot.services import BotService
from apps.courses.models import Course
from apps.users.models import UserProfile


class JobReviewHandlerTests(TestCase):
    def setUp(self):
        self.waha_client = MagicMock()
        self.waha_client.settings = MagicMock(session_name="test-session")
        self.service = BotService(waha_client=self.waha_client)

    def _authenticate_user(self, chat_id: str) -> UserProfile:
        user = UserProfile.objects.create(phone_number=chat_id, is_authenticated_utfpr=True)
        ConversationState.objects.get_or_create(user=user)
        return user

    def test_authenticated_user_job_review_option_sends_response(self):
        """Opção '2' (review de vagas) deve enviar resposta ao usuário autenticado."""
        chat_id = "5544111111111@c.us"
        self._authenticate_user(chat_id)
        # Opção "2" no menu autenticado = "Ver Review de Vagas".
        self.service.process_message(chat_id, "2", from_me=False)
        self.assertTrue(self.waha_client.send_message.called)

    def test_unauthenticated_user_review_alias_blocked_by_auth_gate(self):
        """Usuário não autenticado usando alias 'review' deve receber mensagem de auth."""
        chat_id = "5544222222222@c.us"
        self.service.process_message(chat_id, "review", from_me=False)
        sent_text = self.waha_client.send_message.call_args[0][1]
        self.assertIn("precisa se cadastrar", sent_text)

    def test_unauthenticated_user_with_selected_course_still_blocked(self):
        """Mesmo com selected_course populado por outro caminho, sem auth o review é bloqueado.

        Regressão: antes do gate explícito em send_review, esse caso vazaria
        review para um aluno não autenticado se um admin/fixture/refactor
        setasse selected_course direto.
        """
        chat_id = "5544555000111@c.us"
        course = Course.objects.create(name="Engenharia", is_active=True)
        user = UserProfile.objects.create(phone_number=chat_id, is_authenticated_utfpr=False)
        state, _ = ConversationState.objects.get_or_create(user=user)
        state.selected_course = course
        state.save(update_fields=["selected_course", "updated_at"])

        self.service.process_message(chat_id, "review", from_me=False)

        sent_text = self.waha_client.send_message.call_args[0][1]
        self.assertIn("precisa se cadastrar", sent_text)

    def test_from_me_true_does_not_process(self):
        chat_id = "5544333333333@c.us"
        self._authenticate_user(chat_id)
        self.service.process_message(chat_id, "2", from_me=True)
        self.assertFalse(self.waha_client.send_message.called)


class JobReviewHandlerNoCourseTests(TestCase):
    """Testes para JobReviewHandler quando o usuário não tem curso selecionado."""

    def setUp(self):
        self.waha_client = MagicMock()
        self.waha_client.settings = MagicMock(session_name="test-session")
        self.service = BotService(waha_client=self.waha_client)

    def test_authenticated_user_without_course_receives_warning(self):
        """Usuário autenticado sem curso deve receber aviso para buscar vagas primeiro."""
        chat_id = "5544444444444@c.us"
        # Usuário autenticado mas sem curso selecionado
        user = UserProfile.objects.create(
            phone_number=chat_id,
            is_authenticated_utfpr=True,
        )
        state, _ = ConversationState.objects.get_or_create(user=user)
        state.selected_course = None
        state.save(update_fields=["selected_course", "updated_at"])
        self.service.process_message(chat_id, "2", from_me=False)
        sent_text = self.waha_client.send_message.call_args[0][1]
        # Deve mencionar buscar vagas ou curso
        self.assertTrue(
            "curso" in sent_text.lower()
            or "opção" in sent_text.lower()
            or "buscar" in sent_text.lower()
        )

    @patch("apps.jobs.services.build_review_for_user")
    def test_authenticated_user_with_course_but_no_jobs_sends_empty_message(
        self, mock_build_review
    ):
        """Usuário com curso mas sem vagas deve receber mensagem de 'nenhuma vaga'."""
        mock_build_review.return_value = []

        chat_id = "5544555555555@c.us"
        course = Course.objects.create(name="Ciência da Computação", is_active=True)
        user = UserProfile.objects.create(
            phone_number=chat_id,
            is_authenticated_utfpr=True,
        )
        state, _ = ConversationState.objects.get_or_create(user=user)
        state.selected_course = course
        state.save(update_fields=["selected_course", "updated_at"])
        self.service.process_message(chat_id, "2", from_me=False)
        # Deve ter enviado alguma mensagem (busca em progresso + resultado)
        self.assertTrue(self.waha_client.send_message.called)
