from datetime import date, timedelta

from unittest.mock import MagicMock

from django.test import TestCase

from apps.bot.models import ConversationState
from apps.bot.services import BotService
from apps.courses.models import Course, SearchTerm
from apps.jobs.models import DailyJob, JobSearchLog
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

    def test_perform_search_creates_job_search_log(self):
        """METR-01/D-17: perform_search cria JobSearchLog consultando DailyJob."""
        chat_id = "5522777777777@c.us"
        user = UserProfile.objects.create(phone_number=chat_id, is_authenticated_utfpr=True)
        ConversationState.objects.get_or_create(user=user)
        course = Course.objects.create(name="Engenharia de Software", is_active=True)
        st = SearchTerm.objects.create(course=course, term="python developer")
        DailyJob.objects.create(
            search_term=st,
            fetched_date=date.today(),
            title="Python Dev",
            company="Corp",
            job_url="https://example.com/job/1",
        )
        handler = self.service.job_handler
        handler.perform_search(user, chat_id, [st], term_name="python developer")

        logs = JobSearchLog.objects.filter(user=user)
        self.assertEqual(logs.count(), 1)
        log = logs.first()
        self.assertEqual(log.search_term, "python developer")
        self.assertEqual(log.results_count, 1)
        self.assertIsInstance(log.filters, dict)


class CoursePreferenceTests(TestCase):
    """Testes para persistência de preferência de curso (PERF-01, PERF-02)."""

    def setUp(self):
        self.waha_client = MagicMock()
        self.waha_client.settings = MagicMock(session_name="test-session")
        self.job_service = MagicMock()
        self.service = BotService(waha_client=self.waha_client, job_service=self.job_service)
        self.chat_id = "5541999900001@c.us"
        self.course = Course.objects.create(
            name="Engenharia de Software",
            is_active=True,
            order=1,
        )

    def _authenticate_user(self, phone_number: str | None = None) -> UserProfile:
        phone = phone_number or self.chat_id
        user = UserProfile.objects.create(phone_number=phone, is_authenticated_utfpr=True)
        ConversationState.objects.get_or_create(user=user)
        return user

    def test_first_selection_saves_course(self):
        """PERF-01/D-01: 1ª seleção salva user.course automaticamente."""
        user = self._authenticate_user("5541999900002@c.us")
        self.assertIsNone(user.course)  # pré-condição

        handler = self.service.job_handler
        handler.handle_course_selection(user, "5541999900002@c.us", "1")
        user.refresh_from_db()
        self.assertEqual(user.course, self.course)

    def test_first_selection_sends_preference_saved_message(self):
        """PERF-01/D-02: 1ª seleção envia mensagem com 'salvo como preferência'."""
        user = self._authenticate_user("5541999900003@c.us")
        handler = self.service.job_handler
        handler.handle_course_selection(user, "5541999900003@c.us", "1")
        calls = [str(call) for call in self.waha_client.send_message.call_args_list]
        self.assertTrue(
            any("preferência" in call or "salvo" in call for call in calls),
            f"Mensagem de preferência não encontrada nas chamadas: {calls}",
        )

    def test_subsequent_selection_is_silent(self):
        """PERF-01/D-02: Seleção subsequente não envia mensagem de preferência."""
        user = self._authenticate_user("5541999900004@c.us")
        user.course = self.course
        user.save(update_fields=["course"])
        self.waha_client.send_message.reset_mock()

        handler = self.service.job_handler
        handler.handle_course_selection(user, "5541999900004@c.us", "1")

        calls = [str(call) for call in self.waha_client.send_message.call_args_list]
        self.assertFalse(
            any("preferência" in call or "salvo como" in call for call in calls),
            f"Mensagem de preferência NÃO deveria ser enviada, mas foi: {calls}",
        )

    def test_course_change_sends_updated_message(self):
        """PERF-01/D-06: Troca de curso é silenciosa em handle_course_selection (aviso de troca é no menu)."""
        user = self._authenticate_user("5541999900005@c.us")
        user.course = self.course
        user.save(update_fields=["course"])
        self.waha_client.send_message.reset_mock()

        handler = self.service.job_handler
        handler.handle_course_selection(user, "5541999900005@c.us", "1")
        user.refresh_from_db()
        self.assertEqual(user.course, self.course)  # mesmo curso — confirmação que save ocorreu

    def test_skip_course_selection_when_preference_saved(self):
        """PERF-02/D-03: user.course preenchido → start_course_selection não exibe menu."""
        user = self._authenticate_user("5541999900006@c.us")
        user.course = self.course
        user.save(update_fields=["course"])
        self.waha_client.send_message.reset_mock()

        handler = self.service.job_handler
        handler.start_course_selection(user, "5541999900006@c.us")

        calls = [str(call) for call in self.waha_client.send_message.call_args_list]
        self.assertFalse(
            any("Selecione seu Curso" in call for call in calls),
            "Menu de seleção NÃO deveria ser exibido quando preferência está salva",
        )

    def test_conversation_state_synced_on_skip(self):
        """PERF-02: conversation_state.selected_course sincronizado com user.course no skip."""
        user = self._authenticate_user("5541999900007@c.us")
        user.course = self.course
        user.save(update_fields=["course"])

        handler = self.service.job_handler
        handler.start_course_selection(user, "5541999900007@c.us")

        conv_state = ConversationState.objects.get(user=user)
        self.assertEqual(conv_state.selected_course, self.course)


class PerformSearchDailyJobTests(TestCase):
    """Testes para perform_search() usando DailyJob pré-fetched (BOT-03)."""

    def setUp(self):
        self.waha_client = MagicMock()
        self.waha_client.settings = MagicMock(session_name="test-session")
        self.service = BotService(waha_client=self.waha_client)
        self.chat_id = "5541999910001@c.us"
        self.user = UserProfile.objects.create(
            phone_number=self.chat_id, is_authenticated_utfpr=True
        )
        ConversationState.objects.get_or_create(user=self.user)
        self.course = Course.objects.create(name="Engenharia de Software", is_active=True)
        self.st = SearchTerm.objects.create(course=self.course, term="python developer")

    def test_perform_search_returns_daily_jobs(self):
        """BOT-03: perform_search envia vagas de DailyJob ao WhatsApp."""
        DailyJob.objects.create(
            search_term=self.st,
            fetched_date=date.today(),
            title="Dev Python Senior",
            company="Corp LTDA",
            job_url="https://example.com/job/123",
        )
        handler = self.service.job_handler
        handler.perform_search(self.user, self.chat_id, [self.st], term_name="python developer")
        sent_texts = [call[0][1] for call in self.waha_client.send_message.call_args_list]
        result_text = " ".join(sent_texts)
        self.assertIn("Dev Python Senior", result_text)
        self.assertIn("https://example.com/job/123", result_text)

    def test_perform_search_fallback_to_yesterday(self):
        """BOT-03: Fallback para ontem quando não há vagas hoje (antes das 07:00)."""
        yesterday = date.today() - timedelta(days=1)
        DailyJob.objects.create(
            search_term=self.st,
            fetched_date=yesterday,
            title="Vaga de Ontem",
            company="Corp",
            job_url="https://example.com/job/456",
        )
        handler = self.service.job_handler
        handler.perform_search(self.user, self.chat_id, [self.st], term_name="python developer")
        sent_texts = [call[0][1] for call in self.waha_client.send_message.call_args_list]
        result_text = " ".join(sent_texts)
        self.assertIn("Vaga de Ontem", result_text)

    def test_perform_search_creates_job_search_log_with_user(self):
        """BOT-03/METR-01: perform_search cria JobSearchLog com user=user."""
        DailyJob.objects.create(
            search_term=self.st,
            fetched_date=date.today(),
            title="Dev",
            company="Corp",
            job_url="https://example.com/job/789",
        )
        handler = self.service.job_handler
        handler.perform_search(self.user, self.chat_id, [self.st], term_name="python developer")
        logs = JobSearchLog.objects.filter(user=self.user)
        self.assertEqual(logs.count(), 1)
        self.assertEqual(logs.first().search_term, "python developer")

    def test_perform_search_no_jobs_sends_no_jobs_message(self):
        """BOT-03: Sem DailyJob no banco, bot envia mensagem de nenhuma vaga."""
        handler = self.service.job_handler
        handler.perform_search(self.user, self.chat_id, [self.st], term_name="python developer")
        self.assertEqual(self.waha_client.send_message.call_count, 2)
