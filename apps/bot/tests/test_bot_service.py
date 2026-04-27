from unittest.mock import MagicMock

from django.test import TestCase

from apps.bot.services import BotService
from apps.courses.models import Course, SearchTerm
from apps.users.models import UserProfile


class BotServiceMenuTests(TestCase):
    def setUp(self):
        self.waha_client = MagicMock()
        self.waha_client.settings = MagicMock(session_name="test-session")
        self.service = BotService(waha_client=self.waha_client)

    def test_new_user_receives_menu_prompt(self):
        chat_id = "5511999999999@c.us"
        self.service.process_message(chat_id, "oi", from_me=False)

        sent_text = self.waha_client.send_message.call_args[0][1]
        self.assertIn("IterBot", sent_text)
        self.assertIn("1️⃣ Fazer Cadastro/Login", sent_text)

    def test_logout_clears_state(self):
        user = UserProfile.objects.create(
            phone_number="5511999999999@c.us", is_authenticated_utfpr=True
        )
        self.service.process_message(user.phone_number, "logout", from_me=False)

        user.refresh_from_db()
        self.assertIsNone(user.conversation_state.current_action)
        self.assertIsNone(user.conversation_state.selected_course)
        self.assertIsNone(user.conversation_state.selected_term)
        sent_text = self.waha_client.send_message.call_args[0][1]
        self.assertIn("saiu do sistema", sent_text)


class BotServiceFlowTests(TestCase):
    def setUp(self):
        self.waha_client = MagicMock()
        self.waha_client.settings = MagicMock(session_name="test-session")
        self.job_service = MagicMock()
        self.service = BotService(waha_client=self.waha_client, job_service=self.job_service)

    def _authenticate_user(self, chat_id: str) -> UserProfile:
        user = UserProfile.objects.create(phone_number=chat_id, is_authenticated_utfpr=True)
        return user

    def test_login_flow_with_option_one(self):
        chat_id = "5511888777666@c.us"
        self.service.process_message(chat_id, "1", from_me=False)

        user = UserProfile.objects.get(phone_number=chat_id)
        self.assertEqual(user.conversation_state.current_action, "login_step_ra")

        self.service.process_message(chat_id, "ra123", from_me=False)
        user.refresh_from_db()
        self.assertEqual(user.conversation_state.current_action, "login_step_password")

        self.service.auth_service.authenticate = MagicMock(return_value=True)
        self.service.process_message(chat_id, "senha123", from_me=False)

        user.refresh_from_db()
        self.assertEqual(user.conversation_state.current_action, "login_step_email")
        self.assertEqual(user.conversation_state.flow_data.get("temp_ra"), "ra123")

    def test_course_and_term_selection_drives_job_search(self):
        course = Course.objects.create(name="Engenharia", is_active=True)
        SearchTerm.objects.create(course=course, term="Python", priority=2)
        SearchTerm.objects.create(course=course, term="Django", priority=1)

        chat_id = "5511999990000@c.us"
        user = self._authenticate_user(chat_id)

        # Menu autenticado: opcao 1 = Buscar Vagas
        self.service.process_message(chat_id, "1", from_me=False)  # select course
        user.refresh_from_db()
        self.assertEqual(user.conversation_state.current_action, "course_selection")

        self.service.process_message(chat_id, "1", from_me=False)  # pick first course
        user.refresh_from_db()
        self.assertEqual(user.conversation_state.current_action, "term_selection")
        self.assertEqual(user.conversation_state.selected_course, course)

        self.job_service.search.return_value = [
            {"company": "Capy Corp", "title": "Dev", "url": "https://example.com"}
        ]
        self.service.process_message(chat_id, "1", from_me=False)  # pick top priority term

        user.refresh_from_db()
        self.assertIsNone(user.conversation_state.current_action)
        self.assertEqual(user.conversation_state.selected_term.term, "Python")
        # Bot agora delega kwargs derivados de SearchTerm.to_search_kwargs() e
        # cap em BOT_RESULTS_PER_TERM=5 por mensagem do WhatsApp.
        self.assertEqual(self.job_service.search.call_count, 1)
        _, call_kwargs = self.job_service.search.call_args
        self.assertEqual(call_kwargs["terms"], ["Python"])
        self.assertEqual(call_kwargs["limit"], 5)
        self.assertEqual(call_kwargs["location"], "Curitiba, PR")
        sent_text = self.waha_client.send_message.call_args[0][1]
        self.assertIn("Vagas para Engenharia", sent_text)
        self.assertIn("Python", sent_text)

    def test_option_three_requires_authentication_before_listing_courses(self):
        chat_id = "5511000000000@c.us"

        # No menu nao-autenticado, opcao 3 = Buscar Vagas (cai no auth gate).
        self.service.process_message(chat_id, "3", from_me=False)

        user = UserProfile.objects.get(phone_number=chat_id)
        self.assertFalse(user.is_authenticated_utfpr)

        # Deve enviar mensagem pedindo cadastro antes de listar cursos
        sent_text = self.waha_client.send_message.call_args[0][1]
        self.assertIn("precisa se cadastrar", sent_text)

    def test_option_three_lists_all_active_courses(self):
        course1 = Course.objects.create(name="Engenharia de Software", is_active=True)
        course2 = Course.objects.create(name="Ciência da Computação", is_active=True)
        Course.objects.create(name="Curso Inativo", is_active=False)

        chat_id = "5511999888777@c.us"
        user = self._authenticate_user(chat_id)

        # Menu autenticado: opcao 1 = Buscar Vagas
        self.service.process_message(chat_id, "1", from_me=False)
        user.refresh_from_db()
        self.assertEqual(user.conversation_state.current_action, "course_selection")

        sent_text = self.waha_client.send_message.call_args[0][1]
        self.assertIn("Selecione seu Curso", sent_text)
        self.assertIn(course1.name, sent_text)
        self.assertIn(course2.name, sent_text)
        self.assertNotIn("Curso Inativo", sent_text)

    def test_search_all_terms_option_uses_all_default_terms(self):
        course = Course.objects.create(name="Engenharia", is_active=True)
        SearchTerm.objects.create(course=course, term="Python", priority=2)
        SearchTerm.objects.create(course=course, term="Django", priority=1)

        chat_id = "5511777666555@c.us"
        user = self._authenticate_user(chat_id)

        # Inicia fluxo de curso (opcao 1 do menu autenticado = Buscar Vagas)
        self.service.process_message(chat_id, "1", from_me=False)
        user.refresh_from_db()
        self.assertEqual(user.conversation_state.current_action, "course_selection")

        # Escolhe o primeiro curso
        self.service.process_message(chat_id, "1", from_me=False)
        user.refresh_from_db()
        self.assertEqual(user.conversation_state.current_action, "term_selection")

        # Configura retorno de busca e escolhe opção "Buscar Todos"
        self.job_service.search.return_value = [
            {"company": "Empresa X", "title": "Dev Python", "url": "https://example.com"}
        ]

        # Há 2 termos default, então opção 3 corresponde a "Buscar Todos"
        self.service.process_message(chat_id, "3", from_me=False)

        # Bot agora chama search() uma vez por SearchTerm para respeitar a
        # configuração individual (location/is_remote/job_type/etc.) — antes
        # passava todos os termos numa única chamada com defaults hardcoded.
        self.assertEqual(self.job_service.search.call_count, 2)
        called_terms = [call.kwargs["terms"] for call in self.job_service.search.call_args_list]
        self.assertEqual(called_terms, [["Python"], ["Django"]])

    def test_company_menu_option_opens_onboarding_submenu(self):
        chat_id = "5511999000111@c.us"

        self.service.process_message(chat_id, "2", from_me=False)

        user = UserProfile.objects.get(phone_number=chat_id)
        self.assertEqual(user.conversation_state.current_action, "company_onboarding_selection")
        sent_text = self.waha_client.send_message.call_args[0][1]
        self.assertIn("Cadastrar empresa", sent_text)
        self.assertIn("Ja tenho conta / publicar vaga", sent_text)

    def test_company_onboarding_new_company_contains_signup_link(self):
        chat_id = "5511999000222@c.us"

        with self.settings(PORTAL_BASE_URL="https://52-201-248-14.sslip.io"):
            self.service.process_message(chat_id, "2", from_me=False)
            self.waha_client.send_message.reset_mock()

            self.service.process_message(chat_id, "1", from_me=False)

        sent_text = self.waha_client.send_message.call_args[0][1]
        self.assertIn("/empresas/signup/", sent_text)

    def test_company_onboarding_existing_company_contains_login_and_new_job(self):
        chat_id = "5511999000333@c.us"

        with self.settings(PORTAL_BASE_URL="https://52-201-248-14.sslip.io"):
            self.service.process_message(chat_id, "2", from_me=False)
            self.waha_client.send_message.reset_mock()

            self.service.process_message(chat_id, "2", from_me=False)

        sent_text = self.waha_client.send_message.call_args[0][1]
        self.assertIn("/empresas/login/", sent_text)
        self.assertIn("/empresas/vagas/nova/", sent_text)

    def test_company_onboarding_with_invalid_portal_base_url_sends_unavailable_message(self):
        chat_id = "5511999000444@c.us"

        with self.settings(PORTAL_BASE_URL="localhost:8000"):
            self.service.process_message(chat_id, "2", from_me=False)
            self.waha_client.send_message.reset_mock()

            self.service.process_message(chat_id, "1", from_me=False)

        sent_text = self.waha_client.send_message.call_args[0][1]
        self.assertIn("Portal de empresas temporariamente indisponivel", sent_text)
        self.assertNotIn("localhost:8000", sent_text)

    def test_authenticated_menu_routes_match_displayed_options(self):
        """Menu autenticado: 1=Buscar | 2=Review | 3=Logout. Aliases textuais coexistem."""
        chat_id = "5511999000555@c.us"
        user = self._authenticate_user(chat_id)

        self.service.job_handler.start_course_selection = MagicMock()
        self.service.review_handler.send_review = MagicMock()
        self.service.auth_handler.handle_logout = MagicMock()

        self.service.process_message(chat_id, "1", from_me=False)
        self.service.job_handler.start_course_selection.assert_called_once_with(user, chat_id)

        self.service.process_message(chat_id, "2", from_me=False)
        self.service.review_handler.send_review.assert_called_once_with(user, chat_id)

        self.service.process_message(chat_id, "3", from_me=False)
        self.service.auth_handler.handle_logout.assert_called_once_with(user, chat_id)
