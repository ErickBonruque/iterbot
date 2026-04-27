from django.test import TestCase

from apps.bot.services import BotService
from apps.courses.models import Course, SearchTerm
from apps.users.models import UserProfile
from infra.waha.protocols import (  # noqa: TC001
    Authenticator,
    EmailConfirmationDispatcher,
    JobSearcher,
    MessageSender,
)


class StubMessageSender:
    def __init__(self) -> None:
        self.messages: list[tuple[str, str]] = []
        self.settings = type("Settings", (), {"session_name": "stub-session"})()

    def send_message(self, chat_id: str, text: str) -> bool:
        self.messages.append((chat_id, text))
        return True


class StubJobSearcher:
    def __init__(self) -> None:
        self.calls: list[tuple[list[str], int]] = []

    def search(self, terms: list[str], **kwargs):
        # limit_override do bot vira kwarg `limit`; default 5 do
        # SearchTerm.results_wanted quando não sobrescrito.
        self.calls.append((terms, kwargs.get("limit", 5)))
        return [{"company": "Capy", "title": "Dev", "url": "https://example.com"}]


class StubAuthenticator:
    def __init__(self) -> None:
        self.authenticate_calls: list[tuple[str, str]] = []
        self.logout_calls: list[str] = []

    def authenticate(self, ra: str, password: str) -> bool:
        self.authenticate_calls.append((ra, password))
        return True

    def link_user(self, phone_number: str, ra: str, password: str, email: str | None = None):
        user, _ = UserProfile.objects.get_or_create(phone_number=phone_number)
        user.ra = ra
        user.email = email
        user.is_authenticated_utfpr = False
        user.email_verified = False
        user.save(update_fields=["ra", "email", "is_authenticated_utfpr", "email_verified"])
        return user

    def resend_confirmation(self, phone_number: str) -> bool:
        return True

    def logout(self, phone_number: str) -> bool:
        self.logout_calls.append(phone_number)
        return True


class StubEmailDispatcher:
    def __init__(self) -> None:
        self.dispatched_user_ids: list[int] = []

    def dispatch_confirmation_email(self, user_id: int) -> None:
        self.dispatched_user_ids.append(user_id)


class ProtocolDITests(TestCase):
    def setUp(self):
        self.sender: MessageSender = StubMessageSender()
        self.searcher: JobSearcher = StubJobSearcher()
        self.auth: Authenticator = StubAuthenticator()
        self.dispatcher: EmailConfirmationDispatcher = StubEmailDispatcher()
        self.service = BotService(
            waha_client=self.sender,
            job_service=self.searcher,
            auth_service=self.auth,
            email_dispatcher=self.dispatcher,
        )

    def test_bot_service_works_with_protocol_doubles(self):
        chat_id = "5511999999999@c.us"
        self.service.process_message(chat_id, "oi", from_me=False)

        sent_texts = [text for _, text in self.sender.messages]
        self.assertTrue(any("IterBot" in text for text in sent_texts))

    def test_course_search_uses_injected_job_searcher_double(self):
        course = Course.objects.create(name="Engenharia", is_active=True)
        SearchTerm.objects.create(course=course, term="Python", priority=1)

        chat_id = "5511888777666@c.us"
        UserProfile.objects.create(phone_number=chat_id, is_authenticated_utfpr=True)

        # Menu autenticado: opcao 1 = Buscar Vagas
        self.service.process_message(chat_id, "1", from_me=False)
        self.service.process_message(chat_id, "1", from_me=False)
        self.service.process_message(chat_id, "1", from_me=False)

        self.assertEqual(self.searcher.calls, [(["Python"], 5)])
