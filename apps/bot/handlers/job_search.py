import structlog
from typing import List

from apps.courses.models import Course, SearchTerm
from apps.users.models import UserProfile
from infra.jobspy.service import JobSearchService

from .base import BaseHandler

logger = structlog.get_logger(__name__)


class JobSearchHandler(BaseHandler):
    """Manipula o fluxo de busca de vagas (seleção de curso e termos)."""

    def __init__(self, waha_client, job_service: JobSearchService | None = None) -> None:
        """Inicializa o handler de busca de vagas."""
        super().__init__(waha_client)
        self.job_service = job_service or JobSearchService()

    def _format_course_line(self, index: int, course: Course) -> str:
        """Monta uma linha amigável com informações do curso."""

        detalhes: List[str] = []
        if course.code:
            detalhes.append(course.code)
        if course.level:
            detalhes.append(course.level)
        if course.modality:
            detalhes.append(course.modality)
        if course.duration:
            detalhes.append(f"{course.duration} períodos")

        detalhe_str = f" ({' · '.join(detalhes)})" if detalhes else ""
        descricao = f" – {course.description}" if getattr(course, "description", None) else ""

        return f"*{index + 1}*) {course.name}{detalhe_str}{descricao}"

    def start_course_selection(self, user: UserProfile, chat_id: str) -> None:
        """Inicia o fluxo de seleção de curso."""

        if not user.is_authenticated_utfpr:
            self.send_msg(
                user,
                chat_id,
                "🔒 Você precisa se cadastrar primeiro (Opção 1).",
            )
            return

        courses = list(Course.objects.filter(is_active=True).order_by("order", "name"))
        if not courses:
            self.send_msg(user, chat_id, "⚠️ Nenhum curso cadastrado no sistema.")
            return

        menu_lines = [self._format_course_line(i, c) for i, c in enumerate(courses)]
        msg = (
            "🎓 *Selecione seu Curso*:\n\n"
            + "\n".join(menu_lines)
            + "\n\nDigite o número correspondente:"
        )

        user.current_action = "course_selection"
        user.save(update_fields=["current_action", "last_activity"])
        self.send_msg(user, chat_id, msg)
        logger.info("course_selection_started", user_id=user.id, total_courses=len(courses))

    def _get_active_courses(self) -> list[Course]:
        """Retorna a lista de cursos ativos ordenados."""
        return list(Course.objects.filter(is_active=True).order_by("order", "name"))

    def handle_course_selection(self, user: UserProfile, chat_id: str, text: str) -> None:
        """Processa a escolha de curso pelo usuário."""

        courses = self._get_active_courses()
        try:
            idx = int(text) - 1
        except ValueError:
            self.send_msg(user, chat_id, "❌ Digite apenas o número do curso.")
            return

        if not (0 <= idx < len(courses)):
            self.send_msg(user, chat_id, "❌ Número inválido. Tente novamente.")
            return

        course = courses[idx]
        user.selected_course = course
        user.save(update_fields=["selected_course"])
        self.start_term_selection(user, chat_id)

    def start_term_selection(self, user: UserProfile, chat_id: str) -> None:
        """Inicia a seleção de termos de busca para o curso escolhido."""

        if not user.selected_course:
            self.send_msg(user, chat_id, "❌ Curso não selecionado. Comece novamente pelo menu.")
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
            user.current_action = None
            user.save(update_fields=["current_action", "last_activity"])
            return

        lines = [f"*{i + 1}*) {t.term}" for i, t in enumerate(terms)]
        lines.append(f"*{len(terms) + 1}*) Buscar Todos")

        msg = (
            f"🔍 Curso: *{user.selected_course.name}*\n"
            "Escolha o termo de busca:\n\n"
            + "\n".join(lines)
            + "\n\nDigite o número:"
        )

        user.current_action = "term_selection"
        user.save(update_fields=["current_action", "last_activity"])
        self.send_msg(user, chat_id, msg)
        logger.info(
            "term_selection_started",
            user_id=user.id,
            course_id=user.selected_course.id,
            terms=len(terms),
        )

    def handle_term_selection(self, user: UserProfile, chat_id: str, text: str) -> None:
        """Processa a escolha de termos (um ou todos) e dispara a busca de vagas."""

        if not user.selected_course:
            self.send_msg(user, chat_id, "❌ Curso não selecionado. Comece novamente pelo menu.")
            return

        terms = list(
            user.selected_course.search_terms.filter(is_default=True).order_by("-priority")
        )

        try:
            idx = int(text) - 1
        except ValueError:
            self.send_msg(user, chat_id, "❌ Digite apenas o número.")
            return

        if idx == len(terms):
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

        # Limpa estado e executa busca
        user.current_action = None
        user.save(update_fields=["current_action", "last_activity"])

        self.perform_search(user, chat_id, selected_terms_list, term_name)

    def perform_search(
        self, user: UserProfile, chat_id: str, terms: List[str], term_name: str
    ) -> None:
        """Executa a busca de vagas e envia o resumo das oportunidades."""

        self.send_msg(
            user,
            chat_id,
            f"🔎 Buscando vagas para: *{term_name}*... Aguarde.",
        )

        try:
            jobs = self.job_service.search(terms, limit=5)
        except Exception as exc:  # pragma: no cover - log defensivo
            logger.error(
                "job_search_failed",
                user_id=user.id,
                terms=terms,
                error=str(exc),
                exc_info=True,
            )
            jobs = []

        if not jobs:
            self.send_msg(
                user,
                chat_id,
                "😔 Nenhuma vaga encontrada no momento para esses termos.",
            )
            return

        header = f"🚀 *Vagas para {user.selected_course.name}* (termo: *{term_name}*)"
        lines = [header]
        for job in jobs:
            title = job.get("title", "Vaga")
            company = job.get("company", "Empresa")
            url = job.get("url", "#")
            lines.append(
                f"\n💼 *{title}*\n"
                f"🏢 {company}\n"
                f"🔗 {url}"
            )

        self.send_msg(user, chat_id, "\n".join(lines))

    def handle(self, user: UserProfile, chat_id: str, text: str) -> bool:
        """Despacha mensagens de acordo com o estado atual do usuário."""

        if user.current_action == "course_selection":
            self.handle_course_selection(user, chat_id, text)
            return True

        if user.current_action == "term_selection":
            self.handle_term_selection(user, chat_id, text)
            return True

        return False
