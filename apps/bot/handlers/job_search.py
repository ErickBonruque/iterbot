import structlog

from apps.bot.messages import BOT_MESSAGES
from apps.bot.models import ConversationState
from apps.bot.state_machine import (
    STATE_COURSE_SELECTION,
    STATE_IDLE,
    STATE_TERM_SELECTION,
    apply_state_transition,
    normalize_current_action,
)
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

        # NOVO: skip silencioso quando preferência já salva (PERF-02 / D-03)
        if user.course is not None:
            conversation_state = self._get_conversation_state(user)
            if conversation_state.selected_course_id != user.course_id:
                conversation_state.selected_course = user.course
                conversation_state.save(update_fields=["selected_course", "updated_at"])
            logger.info(
                "course_selection_skipped",
                user_id=user.id,
                course_id=user.course_id,
            )
            self.start_term_selection(user, chat_id)
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
        apply_state_transition(
            conversation_state=conversation_state,
            next_state=STATE_COURSE_SELECTION,
        )
        self.send_msg(user, chat_id, msg)
        logger.info("course_selection_started", user_id=user.id, total_courses=len(courses))

    def start_course_change(self, user: UserProfile, chat_id: str) -> None:
        """Inicia o fluxo de troca de curso preferido via menu principal (D-05/D-06).

        Sempre exibe o menu de seleção, independente de user.course estar preenchido.
        Após a seleção, handle_course_selection() detectará que não é primeira vez
        (user.course != None) e salvará silenciosamente (ou enviará course_preference_updated
        se o curso for diferente).
        """
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
                    BOT_MESSAGES.search.no_courses.key,
                    BOT_MESSAGES.search.no_courses.text,
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
        apply_state_transition(
            conversation_state=conversation_state,
            next_state=STATE_COURSE_SELECTION,
        )
        self.send_msg(user, chat_id, msg)
        logger.info(
            "course_change_started",
            user_id=user.id,
            current_course_id=user.course_id,
        )

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

        is_first_time = user.course is None  # detecta ANTES de salvar
        old_course_id = user.course_id  # None se primeira vez, ID atual se troca

        # NOVO: salvar preferência persistente (D-01)
        user.course = courses[idx]
        user.save(update_fields=["course"])  # atômico, só o campo necessário

        conversation_state = self._get_conversation_state(user)
        conversation_state.selected_course = courses[idx]
        conversation_state.save(update_fields=["selected_course", "updated_at"])

        # NOVO: aviso apenas na 1ª vez (D-02); troca diferente envia course_preference_updated (D-06)
        if is_first_time:
            self.send_msg(
                user,
                chat_id,
                self.resolve_message(
                    BOT_MESSAGES.search.course_preference_saved.key,
                    BOT_MESSAGES.search.course_preference_saved.text,
                    course_name=courses[idx].name,
                ),
            )
        elif old_course_id != courses[idx].id:
            # Troca para curso diferente (via menu "Trocar Curso") — D-06
            self.send_msg(
                user,
                chat_id,
                self.resolve_message(
                    BOT_MESSAGES.search.course_preference_updated.key,
                    BOT_MESSAGES.search.course_preference_updated.text,
                    course_name=courses[idx].name,
                ),
            )
        logger.info(
            "course_preference_saved",
            user_id=user.id,
            course_id=courses[idx].id,
            is_first_time=is_first_time,
        )
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
            apply_state_transition(
                conversation_state=conversation_state,
                next_state=STATE_IDLE,
            )
            return

        lines = [f"*{i + 1}*) {t.term}" for i, t in enumerate(terms)]
        lines.append(f"*{len(terms) + 1}*) Buscar Todos")
        msg = self.resolve_message(
            BOT_MESSAGES.search.term_selection_intro.key,
            BOT_MESSAGES.search.term_selection_intro.text,
            course_name=selected_course.name,
            terms_menu="\n".join(lines),
        )

        apply_state_transition(
            conversation_state=conversation_state,
            next_state=STATE_TERM_SELECTION,
        )
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
            selected_search_terms = terms
            term_name = "Todos os termos"
        elif 0 <= idx < len(terms):
            term = terms[idx]
            conversation_state.selected_term = term
            conversation_state.save(update_fields=["selected_term", "updated_at"])
            selected_search_terms = [term]
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

        apply_state_transition(
            conversation_state=conversation_state,
            next_state=STATE_IDLE,
        )
        self.perform_search(user, chat_id, selected_search_terms, term_name)

    # Limite de vagas retornadas por termo ao usuário do WhatsApp (UX: evita
    # mensagens muito longas mesmo que o SearchTerm.results_wanted seja maior).
    BOT_RESULTS_PER_TERM = 5

    def perform_search(
        self,
        user: UserProfile,
        chat_id: str,
        search_terms: list,
        term_name: str,
    ) -> None:
        """Executa a busca respeitando a configuração de cada SearchTerm.

        Antes o bot chamava `job_service.search(terms, limit=5)` e ignorava
        location/is_remote/job_type/country_indeed/site_name configurados no
        admin — divergindo do "Testar busca" e retornando 0 vagas quando a
        config fugia dos defaults (ex.: remoto, país ≠ Brazil, etc.).
        """
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
            jobs: list[dict] = []
            for search_term in search_terms:
                kwargs = search_term.to_search_kwargs(limit_override=self.BOT_RESULTS_PER_TERM)
                jobs.extend(self.job_service.search(terms=[search_term.term], **kwargs))
        except Exception as exc:
            logger.error(
                "job_search_failed",
                user_id=user.id,
                terms=[st.term for st in search_terms],
                error=str(exc),
                exc_info=True,
            )
            self.send_msg(
                user,
                chat_id,
                self.resolve_message(
                    BOT_MESSAGES.search.search_error.key,
                    BOT_MESSAGES.search.search_error.text,
                ),
            )
            return

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
            url = job.get("job_url") or job.get("job_url_direct") or "#"
            lines.append(f"\n💼 *{title}*\n🏢 {company}\n🔗 {url}")

        self.send_msg(user, chat_id, "\n".join(lines))

    def handle(self, user: UserProfile, chat_id: str, text: str) -> bool:
        current_action = normalize_current_action(self._get_conversation_state(user).current_action)
        if current_action == STATE_COURSE_SELECTION:
            self.handle_course_selection(user, chat_id, text)
            return True
        if current_action == STATE_TERM_SELECTION:
            self.handle_term_selection(user, chat_id, text)
            return True
        return False
