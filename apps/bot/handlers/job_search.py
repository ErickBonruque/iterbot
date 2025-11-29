"""Job search handler for course and term selection."""
from typing import List

import structlog

from apps.courses.models import Course, SearchTerm
from apps.jobs.models import JobSearchLog
from apps.users.models import UserProfile
from infra.jobspy.service import JobSearchService

from .base import BaseHandler

logger = structlog.get_logger(__name__)


class JobSearchHandler(BaseHandler):
    """Handles job search flow including course and term selection."""

    def __init__(self, waha_client, job_service: JobSearchService) -> None:
        """
        Initialize job search handler.
        
        Args:
            waha_client: WAHA client for messaging
            job_service: Service for job searching
        """
        super().__init__(waha_client)
        self.job_service = job_service

    def start_course_selection(self, user: UserProfile, chat_id: str) -> None:
        """
        Start course selection flow.
        
        Args:
            user: User profile
            chat_id: WhatsApp chat ID
        """
        if not user.is_authenticated_utfpr:
            self.send_msg(
                user, chat_id, "🔒 Você precisa se cadastrar primeiro (Opção 1)."
            )
            return

        courses = list(Course.objects.filter(is_active=True).order_by("order", "name"))
        if not courses:
            self.send_msg(user, chat_id, "⚠️ Nenhum curso cadastrado no sistema.")
            return

        menu_lines = [f"*{idx+1}*) {course.name}" for idx, course in enumerate(courses)]
        msg = (
            "🎓 **Selecione seu Curso**:\n\n"
            + "\n".join(menu_lines)
            + "\n\nDigite o número correspondente:"
        )

        user.current_action = "course_selection"
        user.save(update_fields=["current_action", "last_activity"])
        self.send_msg(user, chat_id, msg)

    def handle_course_selection(self, user: UserProfile, chat_id: str, text: str) -> None:
        """
        Handle course selection input.
        
        Args:
            user: User profile
            chat_id: WhatsApp chat ID
            text: User input (course number)
        """
        courses = list(Course.objects.filter(is_active=True).order_by("order", "name"))

        try:
            idx = int(text) - 1
            if 0 <= idx < len(courses):
                course = courses[idx]
                user.selected_course = course
                user.save(update_fields=["selected_course"])
                self.start_term_selection(user, chat_id)
                logger.info("course_selected", user_id=user.id, course=course.name)
            else:
                self.send_msg(user, chat_id, "❌ Número inválido. Tente novamente.")
        except ValueError:
            self.send_msg(user, chat_id, "❌ Digite apenas o número do curso.")

    def start_term_selection(self, user: UserProfile, chat_id: str) -> None:
        """
        Start search term selection flow.
        
        Args:
            user: User profile
            chat_id: WhatsApp chat ID
        """
        if not user.selected_course:
            self.send_msg(user, chat_id, "❌ Erro: curso não selecionado.")
            return

        terms = list(
            user.selected_course.search_terms.filter(is_default=True).order_by("-priority")
        )

        if not terms:
            self.send_msg(
                user,
                chat_id,
                f"⚠️ O curso {user.selected_course.name} não tem termos de busca configurados.",
            )
            self.reset_state(user)
            return

        menu_lines = [f"*{idx+1}*) {term.term}" for idx, term in enumerate(terms)]
        menu_lines.append(f"*{len(terms)+1}*) Buscar Todos")

        msg = (
            f"🔍 Curso: *{user.selected_course.name}*\n"
            "Escolha o termo de busca:\n\n" + "\n".join(menu_lines) + "\n\nDigite o número:"
        )

        user.current_action = "term_selection"
        user.save(update_fields=["current_action", "last_activity"])
        self.send_msg(user, chat_id, msg)

    def handle_term_selection(self, user: UserProfile, chat_id: str, text: str) -> None:
        """
        Handle term selection and initiate search.
        
        Args:
            user: User profile
            chat_id: WhatsApp chat ID
            text: User input (term number)
        """
        if not user.selected_course:
            self.send_msg(user, chat_id, "❌ Erro: curso não selecionado.")
            return

        terms = list(
            user.selected_course.search_terms.filter(is_default=True).order_by("-priority")
        )

        try:
            idx = int(text) - 1
            selected_terms_list: List[str] = []

            if idx == len(terms):  # Search all
                selected_terms_list = [t.term for t in terms]
                term_name = "Todos os termos"
            elif 0 <= idx < len(terms):
                term = terms[idx]
                user.selected_term = term
                user.save(update_fields=["selected_term"])
                selected_terms_list = [term.term]
                term_name = term.term
            else:
                self.send_msg(user, chat_id, "❌ Número inválido.")
                return

            self.reset_state(user)
            self.perform_search(user, chat_id, selected_terms_list, term_name)

        except ValueError:
            self.send_msg(user, chat_id, "❌ Digite apenas o número.")

    def perform_search(
        self, user: UserProfile, chat_id: str, terms: List[str], term_name: str
    ) -> None:
        """
        Execute job search and send results.
        
        Args:
            user: User profile
            chat_id: WhatsApp chat ID
            terms: List of search terms
            term_name: Display name for the search
        """
        self.send_msg(user, chat_id, f"🔎 Buscando vagas para: *{term_name}*... Aguarde.")

        try:
            jobs = self.job_service.search(terms, limit=5)
        except Exception as e:
            logger.error("job_search_failed", user_id=user.id, error=str(e), exc_info=True)
            jobs = []

        # Log the search
        self._log_search(user, terms, jobs)

        if not jobs:
            self.send_msg(
                user,
                chat_id,
                "😔 Nenhuma vaga encontrada no momento para esses termos.",
            )
            return

        msg_lines = [f"🚀 *Vagas Encontradas ({len(jobs)})*:"]
        for job in jobs:
            msg_lines.append(
                f"\n💼 *{job.get('title', 'Vaga')}*\n"
                f"🏢 {job.get('company', 'Empresa')}\n"
                f"🔗 {job.get('url', '#')}"
            )

        self.send_msg(user, chat_id, "\n".join(msg_lines))
        logger.info(
            "job_search_completed",
            user_id=user.id,
            terms=terms,
            results_count=len(jobs),
        )

    def _log_search(self, user: UserProfile, terms: List[str], jobs: List[dict]) -> None:
        """
        Log job search to database.
        
        Args:
            user: User profile
            terms: Search terms used
            jobs: Job results
        """
        try:
            # Create preview of first 5 results
            results_preview = [
                {
                    "title": job.get("title", ""),
                    "company": job.get("company", ""),
                    "url": job.get("url", ""),
                }
                for job in jobs[:5]
            ]

            JobSearchLog.objects.create(
                user=user,
                search_term=", ".join(terms),
                results_count=len(jobs),
                results_preview=results_preview,
            )
        except Exception as e:
            logger.error("failed_to_log_search", user_id=user.id, error=str(e))

    def reset_state(self, user: UserProfile) -> None:
        """
        Reset user conversation state.
        
        Args:
            user: User profile to reset
        """
        user.current_action = None
        user.flow_data = {}
        user.save(update_fields=["current_action", "flow_data", "last_activity"])

    def handle(self, user: UserProfile, chat_id: str, text: str) -> bool:
        """
        Handle job search related messages.
        
        Args:
            user: User profile
            chat_id: WhatsApp chat ID
            text: User message
            
        Returns:
            True if message was handled
        """
        action = user.current_action

        if action == "course_selection":
            self.handle_course_selection(user, chat_id, text)
            return True
        elif action == "term_selection":
            self.handle_term_selection(user, chat_id, text)
            return True

        return False
