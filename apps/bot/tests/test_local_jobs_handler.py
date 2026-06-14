"""Testes do menu "Vagas do meu curso" (Fase 3)."""

from unittest.mock import MagicMock

from django.test import TestCase

from apps.bot.models import ConversationState
from apps.bot.services import BotService
from apps.courses.models import Area, Course
from apps.jobs.models import Job, JobStatus
from apps.users.models import UserProfile


class LocalJobsHandlerTests(TestCase):
    def setUp(self):
        self.waha_client = MagicMock()
        self.waha_client.settings = MagicMock(session_name="test-session")
        self.service = BotService(waha_client=self.waha_client)

        self.area = Area.objects.create(name="Tecnologia da Informação Teste")
        self.course = Course.objects.create(
            name="Engenharia de Software", is_active=True, area=self.area
        )
        self.company = None

    def _company(self):
        from apps.jobs.tests.factories import CompanyFactory

        if self.company is None:
            self.company = CompanyFactory()
        return self.company

    def _authenticate_user(self, chat_id: str, with_course: bool = True) -> UserProfile:
        user = UserProfile.objects.create(
            phone_number=chat_id,
            is_authenticated_utfpr=True,
            course=self.course if with_course else None,
        )
        ConversationState.objects.get_or_create(user=user)
        return user

    def _make_job(self, titulo: str, *, areas=None, status=JobStatus.APPROVED) -> Job:
        job = Job.objects.create(
            company=self._company(),
            titulo=titulo,
            descricao=f"Descrição de {titulo}",
            requisitos=f"Requisitos de {titulo}",
            salario="R$ 2.000",
            tipo="Estágio",
            status=status,
        )
        if areas:
            job.areas.set(areas)
        return job

    def _last_text(self) -> str:
        return self.waha_client.send_message.call_args[0][1]

    # --- Gate de autenticação -------------------------------------------------

    def test_unauthenticated_alias_blocked_by_auth_gate(self):
        chat_id = "5577000000001@c.us"
        self.service.process_message(chat_id, "vagas do meu curso", from_me=False)
        self.assertIn("precisa se cadastrar", self._last_text())

    # --- Sem curso ------------------------------------------------------------

    def test_authenticated_without_course_receives_guidance(self):
        chat_id = "5577000000002@c.us"
        self._authenticate_user(chat_id, with_course=False)
        self.service.process_message(chat_id, "3", from_me=False)
        self.assertIn("não escolheu um curso", self._last_text())

    # --- Listagem -------------------------------------------------------------

    def test_lists_approved_jobs_for_course_area(self):
        chat_id = "5577000000003@c.us"
        user = self._authenticate_user(chat_id)
        self._make_job("Estágio Python", areas=[self.area])

        self.service.process_message(chat_id, "3", from_me=False)

        text = self._last_text()
        self.assertIn("Estágio Python", text)
        user.refresh_from_db()
        self.assertEqual(user.conversation_state.current_action, "local_jobs_list")
        self.assertEqual(len(user.conversation_state.flow_data["local_job_ids"]), 1)

    def test_job_without_area_counts_as_all_areas(self):
        chat_id = "5577000000004@c.us"
        self._authenticate_user(chat_id)
        self._make_job("Vaga Geral")  # sem área = todas

        self.service.process_message(chat_id, "3", from_me=False)
        self.assertIn("Vaga Geral", self._last_text())

    def test_job_from_other_area_is_excluded(self):
        chat_id = "5577000000005@c.us"
        self._authenticate_user(chat_id)
        other_area = Area.objects.create(name="Saúde Teste")
        self._make_job("Vaga Saúde", areas=[other_area])

        self.service.process_message(chat_id, "3", from_me=False)
        self.assertIn("não há vagas locais", self._last_text().lower())

    def test_pending_job_is_not_listed(self):
        chat_id = "5577000000006@c.us"
        self._authenticate_user(chat_id)
        self._make_job("Vaga Pendente", areas=[self.area], status=JobStatus.PENDING)

        self.service.process_message(chat_id, "3", from_me=False)
        self.assertIn("não há vagas locais", self._last_text().lower())

    # --- Detalhe --------------------------------------------------------------

    def test_selecting_number_opens_detail(self):
        chat_id = "5577000000007@c.us"
        user = self._authenticate_user(chat_id)
        self._make_job("Estágio Backend", areas=[self.area])

        self.service.process_message(chat_id, "3", from_me=False)
        self.service.process_message(chat_id, "1", from_me=False)

        text = self._last_text()
        self.assertIn("Estágio Backend", text)
        self.assertIn("Descrição de Estágio Backend", text)
        self.assertIn("Requisitos de Estágio Backend", text)
        user.refresh_from_db()
        self.assertEqual(user.conversation_state.current_action, "local_job_detail")

    def test_invalid_selection_number_shows_error(self):
        chat_id = "5577000000008@c.us"
        self._authenticate_user(chat_id)
        self._make_job("Estágio QA", areas=[self.area])

        self.service.process_message(chat_id, "3", from_me=False)
        self.service.process_message(chat_id, "9", from_me=False)
        self.assertIn("inválido", self._last_text().lower())

    def test_non_numeric_selection_shows_error(self):
        chat_id = "5577000000009@c.us"
        self._authenticate_user(chat_id)
        self._make_job("Estágio Dados", areas=[self.area])

        self.service.process_message(chat_id, "3", from_me=False)
        self.service.process_message(chat_id, "abc", from_me=False)
        self.assertIn("inválido", self._last_text().lower())

    # --- Candidatura (encadeia para a Fase 4) --------------------------------

    def test_candidatar_starts_application_flow(self):
        chat_id = "5577000000010@c.us"
        user = self._authenticate_user(chat_id)
        self._make_job("Estágio Mobile", areas=[self.area])

        self.service.process_message(chat_id, "3", from_me=False)
        self.service.process_message(chat_id, "1", from_me=False)
        self.service.process_message(chat_id, "candidatar", from_me=False)

        # Sem mini-perfil → inicia a coleta (Fase 4), não o stub antigo.
        self.assertIn("1/3", self._last_text())
        user.refresh_from_db()
        self.assertEqual(user.conversation_state.current_action, "profile_periodo")

    # --- Escape do fluxo ------------------------------------------------------

    def test_menu_escapes_local_jobs_flow(self):
        chat_id = "5577000000011@c.us"
        user = self._authenticate_user(chat_id)
        self._make_job("Estágio Cloud", areas=[self.area])

        self.service.process_message(chat_id, "3", from_me=False)
        self.service.process_message(chat_id, "menu", from_me=False)

        user.refresh_from_db()
        self.assertIsNone(user.conversation_state.current_action)
