"""Testes do fluxo de candidatura com mini-perfil (Fase 4)."""

from unittest.mock import MagicMock, patch

from django.test import TestCase

from apps.bot.models import ConversationState
from apps.bot.services import BotService
from apps.courses.models import Area, Course
from apps.jobs.models import ApplicationStatus, Job, JobApplication, JobStatus
from apps.users.models import StudentProfile, UserProfile


class ApplicationHandlerTests(TestCase):
    def setUp(self):
        self.waha_client = MagicMock()
        self.waha_client.settings = MagicMock(session_name="test-session")
        self.service = BotService(waha_client=self.waha_client)

        self.area = Area.objects.create(name="TI Candidatura")
        self.course = Course.objects.create(name="Eng. Software", is_active=True, area=self.area)
        from apps.jobs.tests.factories import CompanyFactory

        self.company = CompanyFactory()
        self.job = Job.objects.create(
            company=self.company,
            titulo="Estágio Dev",
            descricao="Desc",
            requisitos="Reqs",
            salario="R$ 2.000",
            tipo="Estágio",
            status=JobStatus.APPROVED,
        )
        self.job.areas.set([self.area])

    def _authenticate_user(self, chat_id: str) -> UserProfile:
        user = UserProfile.objects.create(
            phone_number=chat_id,
            is_authenticated_utfpr=True,
            course=self.course,
            ra="a1234567",
            email="aluno@alunos.utfpr.edu.br",
        )
        ConversationState.objects.get_or_create(user=user)
        return user

    def _open_detail(self, chat_id: str):
        """Navega menu 3 (lista) → 1 (detalhe)."""
        self.service.process_message(chat_id, "3", from_me=False)
        self.service.process_message(chat_id, "1", from_me=False)

    def _last_text(self) -> str:
        return self.waha_client.send_message.call_args[0][1]

    @patch("apps.bot.handlers.application.send_job_application_email")
    def test_full_flow_collects_profile_and_creates_application(self, mock_email):
        chat_id = "5588000000001@c.us"
        user = self._authenticate_user(chat_id)
        self._open_detail(chat_id)

        self.service.process_message(chat_id, "candidatar", from_me=False)
        self.assertIn("1/3", self._last_text())

        self.service.process_message(chat_id, "5º período", from_me=False)
        self.assertIn("2/3", self._last_text())

        self.service.process_message(chat_id, "Python, Django", from_me=False)
        self.assertIn("3/3", self._last_text())

        self.service.process_message(chat_id, "https://linkedin.com/in/aluno", from_me=False)
        self.assertIn("Confirme", self._last_text())

        self.service.process_message(chat_id, "confirmar", from_me=False)

        application = JobApplication.objects.get(user=user, job=self.job)
        self.assertEqual(application.status, ApplicationStatus.PENDING)
        self.assertEqual(application.profile_snapshot["periodo"], "5º período")
        self.assertEqual(application.profile_snapshot["skills"], "Python, Django")
        self.assertEqual(
            application.profile_snapshot["linkedin_url"], "https://linkedin.com/in/aluno"
        )
        self.assertIn("enviada", self._last_text().lower())
        mock_email.delay.assert_called_once_with(application.id)

        # Mini-perfil persistido e reutilizável
        profile = StudentProfile.objects.get(user=user)
        self.assertTrue(profile.is_complete)
        user.refresh_from_db()
        self.assertIsNone(user.conversation_state.current_action)

    @patch("apps.bot.handlers.application.send_job_application_email")
    def test_existing_profile_skips_collection(self, mock_email):
        chat_id = "5588000000002@c.us"
        user = self._authenticate_user(chat_id)
        StudentProfile.objects.create(
            user=user, periodo="7º", skills="Go", linkedin_url="https://linkedin.com/in/x"
        )
        self._open_detail(chat_id)

        self.service.process_message(chat_id, "candidatar", from_me=False)
        # Vai direto para confirmação (sem perguntar período)
        self.assertIn("Confirme", self._last_text())

        self.service.process_message(chat_id, "confirmar", from_me=False)
        self.assertTrue(JobApplication.objects.filter(user=user, job=self.job).exists())

    @patch("apps.bot.handlers.application.send_job_application_email")
    def test_duplicate_application_blocked(self, mock_email):
        chat_id = "5588000000003@c.us"
        user = self._authenticate_user(chat_id)
        JobApplication.objects.create(user=user, job=self.job)
        self._open_detail(chat_id)

        self.service.process_message(chat_id, "candidatar", from_me=False)
        self.assertIn("já se candidatou", self._last_text())
        self.assertEqual(JobApplication.objects.filter(user=user, job=self.job).count(), 1)
        mock_email.delay.assert_not_called()

    @patch("apps.bot.handlers.application.send_job_application_email")
    def test_invalid_link_reprompts(self, mock_email):
        chat_id = "5588000000004@c.us"
        self._authenticate_user(chat_id)
        self._open_detail(chat_id)

        self.service.process_message(chat_id, "candidatar", from_me=False)
        self.service.process_message(chat_id, "5º", from_me=False)
        self.service.process_message(chat_id, "Python", from_me=False)
        self.service.process_message(chat_id, "isso não é url", from_me=False)
        self.assertIn("inválido", self._last_text().lower())

    @patch("apps.bot.handlers.application.send_job_application_email")
    def test_skip_link_stores_empty(self, mock_email):
        chat_id = "5588000000005@c.us"
        user = self._authenticate_user(chat_id)
        self._open_detail(chat_id)

        self.service.process_message(chat_id, "candidatar", from_me=False)
        self.service.process_message(chat_id, "5º", from_me=False)
        self.service.process_message(chat_id, "Python", from_me=False)
        self.service.process_message(chat_id, "pular", from_me=False)
        self.service.process_message(chat_id, "confirmar", from_me=False)

        application = JobApplication.objects.get(user=user, job=self.job)
        self.assertEqual(application.profile_snapshot["linkedin_url"], "")
        self.assertEqual(application.profile_snapshot["cv_url"], "")

    @patch("apps.bot.handlers.application.send_job_application_email")
    def test_cancel_aborts_flow(self, mock_email):
        chat_id = "5588000000006@c.us"
        user = self._authenticate_user(chat_id)
        self._open_detail(chat_id)

        self.service.process_message(chat_id, "candidatar", from_me=False)
        self.service.process_message(chat_id, "cancelar", from_me=False)

        self.assertFalse(JobApplication.objects.filter(user=user, job=self.job).exists())
        user.refresh_from_db()
        self.assertIsNone(user.conversation_state.current_action)

    @patch("apps.bot.handlers.application.send_job_application_email")
    def test_email_dispatch_failure_does_not_break_flow(self, mock_email):
        """Broker indisponível: candidatura ainda é criada (degradação graciosa)."""
        chat_id = "5588000000007@c.us"
        user = self._authenticate_user(chat_id)
        StudentProfile.objects.create(user=user, periodo="7º", skills="Go")
        mock_email.delay.side_effect = RuntimeError("broker down")
        self._open_detail(chat_id)

        self.service.process_message(chat_id, "candidatar", from_me=False)
        self.service.process_message(chat_id, "confirmar", from_me=False)

        self.assertTrue(JobApplication.objects.filter(user=user, job=self.job).exists())
        self.assertIn("enviada", self._last_text().lower())
