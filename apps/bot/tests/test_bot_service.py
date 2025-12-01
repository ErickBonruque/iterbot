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
        self.assertIn("CapyVagas", sent_text)
        self.assertIn("Opção 1", sent_text)

    def test_logout_clears_state(self):
        user = UserProfile.objects.create(phone_number="5511999999999@c.us", is_authenticated_utfpr=True)
        self.service.process_message(user.phone_number, "logout", from_me=False)

        user.refresh_from_db()
        self.assertIsNone(user.current_action)
        self.assertIsNone(user.selected_course)
        self.assertIsNone(user.selected_term)
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
        self.assertEqual(user.current_action, "awaiting_credentials")

        # complete login
        self.service.auth_service.authenticate = MagicMock(return_value=True)
        self.service.process_message(chat_id, "ra123 senha", from_me=False)

        user.refresh_from_db()
        self.assertIsNone(user.current_action)
        self.assertTrue(user.is_authenticated_utfpr)
        self.assertEqual(user.ra, "ra123")

    def test_course_and_term_selection_drives_job_search(self):
        course = Course.objects.create(name="Engenharia", is_active=True)
        SearchTerm.objects.create(course=course, term="Python", priority=2)
        SearchTerm.objects.create(course=course, term="Django", priority=1)

        chat_id = "5511999990000@c.us"
        user = self._authenticate_user(chat_id)

        self.service.process_message(chat_id, "3", from_me=False)  # select course
        user.refresh_from_db()
        self.assertEqual(user.current_action, "course_selection")

        self.service.process_message(chat_id, "1", from_me=False)  # pick first course
        user.refresh_from_db()
        self.assertEqual(user.current_action, "term_selection")
        self.assertEqual(user.selected_course, course)

        self.job_service.search.return_value = [
            {"company": "Capy Corp", "title": "Dev", "url": "https://example.com"}
        ]
        self.service.process_message(chat_id, "1", from_me=False)  # pick top priority term

        user.refresh_from_db()
        self.assertIsNone(user.current_action)
        self.assertEqual(user.selected_term.term, "Python")
        self.job_service.search.assert_called_with(["Python"], limit=5)
        sent_text = self.waha_client.send_message.call_args[0][1]
        self.assertIn("Vagas para Engenharia", sent_text)
        self.assertIn("Python", sent_text)

    def test_option_three_requires_authentication_before_listing_courses(self):
        chat_id = "5511000000000@c.us"

        # Usuário não autenticado tenta acessar opção 3
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

        self.service.process_message(chat_id, "3", from_me=False)
        user.refresh_from_db()
        self.assertEqual(user.current_action, "course_selection")

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

        # Inicia fluxo de curso
        self.service.process_message(chat_id, "3", from_me=False)
        user.refresh_from_db()
        self.assertEqual(user.current_action, "course_selection")

        # Escolhe o primeiro curso
        self.service.process_message(chat_id, "1", from_me=False)
        user.refresh_from_db()
        self.assertEqual(user.current_action, "term_selection")

        # Configura retorno de busca e escolhe opção "Buscar Todos"
        self.job_service.search.return_value = [
            {"company": "Empresa X", "title": "Dev Python", "url": "https://example.com"}
        ]

        # Há 2 termos default, então opção 3 corresponde a "Buscar Todos"
        self.service.process_message(chat_id, "3", from_me=False)

        self.job_service.search.assert_called_with(["Python", "Django"], limit=5)
