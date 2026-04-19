import structlog

from apps.bot.messages import BOT_MESSAGES
from apps.bot.models import ConversationState
from apps.courses.models import Course
from apps.users.models import UserProfile
from infra.waha.protocols import JobSearcher, MessageSender

from .base import BaseHandler

logger = structlog.get_logger(__name__)


class JobSearchHandler(BaseHandler):
    def __init__(self, waha_client: MessageSender, job_service: JobSearcher) -> None:
        super().__init__(waha_client)
        self.job_service = job_service

    def _get_conversation_state(self, user: UserProfile) -> ConversationState:
        conversation_state, _ = ConversationState.objects.get_or_create(user=user)
        return conversation_state

    def _format_course_line(self, index: int, course: Course) -> str:
        details: list[str] = []
        if course.code:
            details.append(course.code)
        if course.level:
            details.append(course.level)
        if course.modality:
            details.append(course.modality)
        if course.duration:
            details.append(f"{course.duration} períodos")

        detail_str = f" ({' · '.join(details)})" if details else ""
        description = f" - {course.description}" if getattr(course, "description", None) else ""
        return f"*{index + 1}*) {course.name}{detail_str}{description}"

    def start_course_selection(self, user: UserProfile, chat_id: str) -> None:
        if not user.is_authenticated_utfpr:
            self.send_msg(
                user,
                chat_id,
                self.resolve_message(
                    BOT_MESSAGES.search.auth_required.key,
                    BOT_MESSAGES.search.auth_required.text,
                ),
            )
            return

        courses = list(Course.objects.filter(is_active=True).order_by("order", "name"))
        if not courses:
            self.send_msg(
                user,
                chat_id,
                self.resolve_message(
                    BOT_MESSAGES.search.no_courses.key, BOT_MESSAGES.search.no_courses.text
                ),
            )
            return

        menu_lines = [self._format_course_line(i, c) for i, c in enumerate(courses)]
        msg = self.resolve_message(
            BOT_MESSAGES.search.selection_intro.key,
            BOT_MESSAGES.search.selection_intro.text,
            courses_menu="\n".join(menu_lines),
        )

        conversation_state = self._get_conversation_state(user)
        conversation_state.current_action = "course_selection"
        conversation_state.save(update_fields=["current_action", "updated_at"])
        self.send_msg(user, chat_id, msg)
        logger.info("course_selection_started", user_id=user.id, total_courses=len(courses))

    def _get_active_courses(self) -> list[Course]:
        return list(Course.objects.filter(is_active=True).order_by("order", "name"))

    def handle_course_selection(self, user: UserProfile, chat_id: str, text: str) -> None:
        courses = self._get_active_courses()
        try:
            idx = int(text) - 1
        except ValueError:
            self.send_msg(
                user,
                chat_id,
                self.resolve_message(
                    BOT_MESSAGES.search.invalid_course_non_numeric.key,
                    BOT_MESSAGES.search.invalid_course_non_numeric.text,
                ),
            )
            return

        if not (0 <= idx < len(courses)):
            self.send_msg(
                user,
                chat_id,
                self.resolve_message(
                    BOT_MESSAGES.search.invalid_course_number.key,
                    BOT_MESSAGES.search.invalid_course_number.text,
                ),
            )
            return

        conversation_state = self._get_conversation_state(user)
        conversation_state.selected_course = courses[idx]
        conversation_state.save(update_fields=["selected_course", "updated_at"])
        self.start_term_selection(user, chat_id)

    def start_term_selection(self, user: UserProfile, chat_id: str) -> None:
        conversation_state = self._get_conversation_state(user)
        selected_course = conversation_state.selected_course
        if not selected_course:
            self.send_msg(
                user,
                chat_id,
                self.resolve_message(
                    BOT_MESSAGES.search.missing_course.key, BOT_MESSAGES.search.missing_course.text
                ),
            )
            return

        terms = list(selected_course.search_terms.filter(is_default=True).order_by("-priority"))
        if not terms:
            self.send_msg(
                user,
                chat_id,
                self.resolve_message(
                    BOT_MESSAGES.search.no_terms_for_course.key,
                    BOT_MESSAGES.search.no_terms_for_course.text,
                    course_name=selected_course.name,
                ),
            )
            conversation_state.current_action = None
            conversation_state.save(update_fields=["current_action", "updated_at"])
            return

        lines = [f"*{i + 1}*) {t.term}" for i, t in enumerate(terms)]
        lines.append(f"*{len(terms) + 1}*) Buscar Todos")
        msg = self.resolve_message(
            BOT_MESSAGES.search.term_selection_intro.key,
            BOT_MESSAGES.search.term_selection_intro.text,
            course_name=selected_course.name,
            terms_menu="\n".join(lines),
        )

        conversation_state.current_action = "term_selection"
        conversation_state.save(update_fields=["current_action", "updated_at"])
        self.send_msg(user, chat_id, msg)
        logger.info(
            "term_selection_started",
            user_id=user.id,
            course_id=selected_course.id,
            terms=len(terms),
        )

    def handle_term_selection(self, user: UserProfile, chat_id: str, text: str) -> None:
        conversation_state = self._get_conversation_state(user)
        selected_course = conversation_state.selected_course

        if not selected_course:
            self.send_msg(
                user,
                chat_id,
                self.resolve_message(
                    BOT_MESSAGES.search.missing_course.key, BOT_MESSAGES.search.missing_course.text
                ),
            )
            return

        terms = list(selected_course.search_terms.filter(is_default=True).order_by("-priority"))
        try:
            idx = int(text) - 1
        except ValueError:
            self.send_msg(
                user,
                chat_id,
                self.resolve_message(
                    BOT_MESSAGES.search.invalid_term_non_numeric.key,
                    BOT_MESSAGES.search.invalid_term_non_numeric.text,
                ),
            )
            return

        if idx == len(terms):
            selected_terms_list = [t.term for t in terms]
            term_name = "Todos os termos"
        elif 0 <= idx < len(terms):
            term = terms[idx]
            conversation_state.selected_term = term
            conversation_state.save(update_fields=["selected_term", "updated_at"])
            selected_terms_list = [term.term]
            term_name = term.term
        else:
            self.send_msg(
                user,
                chat_id,
                self.resolve_message(
                    BOT_MESSAGES.search.invalid_term_number.key,
                    BOT_MESSAGES.search.invalid_term_number.text,
                ),
            )
            return

        conversation_state.current_action = None
        conversation_state.save(update_fields=["current_action", "updated_at"])
        self.perform_search(user, chat_id, selected_terms_list, term_name)

    def perform_search(
        self, user: UserProfile, chat_id: str, terms: list[str], term_name: str
    ) -> None:
        self.send_msg(
            user,
            chat_id,
            self.resolve_message(
                BOT_MESSAGES.search.searching_jobs.key,
                BOT_MESSAGES.search.searching_jobs.text,
                term_name=term_name,
            ),
        )

        try:
            jobs = self.job_service.search(terms, limit=5)
        except Exception as exc:  # pragma: no cover
            logger.error(
                "job_search_failed", user_id=user.id, terms=terms, error=str(exc), exc_info=True
            )
            jobs = []

        if not jobs:
            self.send_msg(
                user,
                chat_id,
                self.resolve_message(
                    BOT_MESSAGES.search.no_jobs.key, BOT_MESSAGES.search.no_jobs.text
                ),
            )
            return

        selected_course = self._get_conversation_state(user).selected_course
        header = self.resolve_message(
            BOT_MESSAGES.search.results_header.key,
            BOT_MESSAGES.search.results_header.text,
            course_name=selected_course.name,
            term_name=term_name,
        )
        lines = [header]
        for job in jobs:
            title = job.get("title", "Vaga")
            company = job.get("company", "Empresa")
            url = job.get("url", "#")
            lines.append(f"\n💼 *{title}*\n🏢 {company}\n🔗 {url}")

        self.send_msg(user, chat_id, "\n".join(lines))

    def handle(self, user: UserProfile, chat_id: str, text: str) -> bool:
        current_action = self._get_conversation_state(user).current_action
        if current_action == "course_selection":
            self.handle_course_selection(user, chat_id, text)
            return True
        if current_action == "term_selection":
            self.handle_term_selection(user, chat_id, text)
            return True
        return False
