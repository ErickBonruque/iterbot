"""Handler do menu "Vagas do meu curso" (opção 3 do menu autenticado).

Lista as vagas locais aprovadas da **área do curso do aluno** e abre o detalhe
de cada vaga. A candidatura em si é a Fase 4 — aqui o comando *candidatar*
responde com um aviso "em breve" (stub).
"""

import structlog

from apps.bot.messages import BOT_MESSAGES
from apps.bot.models import ConversationState
from apps.bot.state_machine import (
    STATE_IDLE,
    STATE_LOCAL_JOB_DETAIL,
    STATE_LOCAL_JOBS_LIST,
    apply_state_transition,
    normalize_current_action,
)
from apps.jobs.models import Job, JobStatus
from apps.jobs.services import get_local_jobs_queryset_for_area
from apps.users.models import UserProfile
from infra.waha.protocols import MessageSender

from .base import BaseHandler

logger = structlog.get_logger(__name__)


class LocalJobsHandler(BaseHandler):
    """Exibe e navega pelas vagas locais da área do curso do aluno."""

    # Limite de vagas listadas de uma vez (UX: mensagem não pode ficar enorme).
    LOCAL_JOBS_LIMIT = 10

    def __init__(self, waha_client: MessageSender, application_handler=None) -> None:
        super().__init__(waha_client)
        # Injetado pelo BotService; permite encadear "candidatar" → Fase 4.
        self.application_handler = application_handler

    def _get_conversation_state(self, user: UserProfile) -> ConversationState:
        conversation_state, _ = ConversationState.objects.get_or_create(user=user)
        return conversation_state

    def send_local_jobs_list(self, user: UserProfile, chat_id: str) -> None:
        # Gate de autenticação alinhado com JobReviewHandler/JobSearchHandler.
        if not user.is_authenticated_utfpr:
            self.send_msg(
                user,
                chat_id,
                self.resolve_message(
                    BOT_MESSAGES.search.auth_required.key,
                    BOT_MESSAGES.search.auth_required.text,
                ),
            )
            logger.info("local_jobs_blocked_unauthenticated", user_id=user.id)
            return

        course = user.course
        if course is None:
            self.send_msg(
                user,
                chat_id,
                self.resolve_message(
                    BOT_MESSAGES.local_jobs.no_course.key,
                    BOT_MESSAGES.local_jobs.no_course.text,
                ),
            )
            logger.info("local_jobs_no_course", user_id=user.id)
            return

        area = course.area  # pode ser None → "vagas para todas as áreas"
        jobs = list(get_local_jobs_queryset_for_area(area)[: self.LOCAL_JOBS_LIMIT])

        if not jobs:
            self.send_msg(
                user,
                chat_id,
                self.resolve_message(
                    BOT_MESSAGES.local_jobs.empty.key,
                    BOT_MESSAGES.local_jobs.empty.text,
                    course_name=course.name,
                ),
            )
            logger.info(
                "local_jobs_empty",
                user_id=user.id,
                area=area.name if area else None,
            )
            return

        menu_lines = [f"*{i}*) {job.titulo} — {job.company.nome}" for i, job in enumerate(jobs, 1)]
        msg = self.resolve_message(
            BOT_MESSAGES.local_jobs.list_intro.key,
            BOT_MESSAGES.local_jobs.list_intro.text,
            course_name=course.name,
            jobs_menu="\n".join(menu_lines),
        )

        conversation_state = self._get_conversation_state(user)
        conversation_state.flow_data["local_job_ids"] = [job.id for job in jobs]
        apply_state_transition(
            conversation_state=conversation_state,
            next_state=STATE_LOCAL_JOBS_LIST,
            update_fields=["flow_data"],
        )
        self.send_msg(user, chat_id, msg)
        logger.info(
            "local_jobs_list_sent",
            user_id=user.id,
            area=area.name if area else None,
            jobs_count=len(jobs),
        )

    def handle_jobs_list_selection(self, user: UserProfile, chat_id: str, text: str) -> None:
        conversation_state = self._get_conversation_state(user)
        job_ids = conversation_state.flow_data.get("local_job_ids", [])

        try:
            idx = int(text.strip()) - 1
        except ValueError:
            self.send_msg(
                user,
                chat_id,
                self.resolve_message(
                    BOT_MESSAGES.local_jobs.invalid_selection.key,
                    BOT_MESSAGES.local_jobs.invalid_selection.text,
                ),
            )
            return

        if not (0 <= idx < len(job_ids)):
            self.send_msg(
                user,
                chat_id,
                self.resolve_message(
                    BOT_MESSAGES.local_jobs.invalid_selection.key,
                    BOT_MESSAGES.local_jobs.invalid_selection.text,
                ),
            )
            return

        job_id = job_ids[idx]
        job = (
            Job.objects.select_related("company")
            .filter(pk=job_id, status=JobStatus.APPROVED)
            .first()
        )
        if job is None:
            # A vaga pode ter sido removida/expirada entre a listagem e a escolha.
            self.send_msg(
                user,
                chat_id,
                self.resolve_message(
                    BOT_MESSAGES.local_jobs.job_unavailable.key,
                    BOT_MESSAGES.local_jobs.job_unavailable.text,
                ),
            )
            apply_state_transition(
                conversation_state=conversation_state,
                next_state=STATE_IDLE,
                clear_flow_data=True,
            )
            return

        conversation_state.flow_data["selected_local_job_id"] = job_id
        apply_state_transition(
            conversation_state=conversation_state,
            next_state=STATE_LOCAL_JOB_DETAIL,
            update_fields=["flow_data"],
        )
        self.send_msg(user, chat_id, self._format_job_detail(job))
        logger.info("local_job_detail_sent", user_id=user.id, job_id=job_id)

    def _format_job_detail(self, job: Job) -> str:
        return self.resolve_message(
            BOT_MESSAGES.local_jobs.detail.key,
            BOT_MESSAGES.local_jobs.detail.text,
            titulo=job.titulo,
            company=job.company.nome,
            salario=job.salario or "A combinar",
            tipo=job.tipo,
            descricao=job.descricao,
            requisitos=job.requisitos or "Não informados",
        )

    def handle_job_detail(self, user: UserProfile, chat_id: str, text: str) -> None:
        conversation_state = self._get_conversation_state(user)
        job_id = conversation_state.flow_data.get("selected_local_job_id")
        job = (
            Job.objects.select_related("company")
            .filter(pk=job_id, status=JobStatus.APPROVED)
            .first()
            if job_id
            else None
        )

        if text.strip() == "candidatar":
            if job is None:
                self.send_msg(
                    user,
                    chat_id,
                    self.resolve_message(
                        BOT_MESSAGES.local_jobs.job_unavailable.key,
                        BOT_MESSAGES.local_jobs.job_unavailable.text,
                    ),
                )
                apply_state_transition(
                    conversation_state=conversation_state,
                    next_state=STATE_IDLE,
                    clear_flow_data=True,
                )
                return
            if self.application_handler is not None:
                self.application_handler.start_application(user, chat_id, job)
                return
            # Fallback (Fase 4 não disponível): stub "em breve".
            self.send_msg(
                user,
                chat_id,
                self.resolve_message(
                    BOT_MESSAGES.local_jobs.apply_coming_soon.key,
                    BOT_MESSAGES.local_jobs.apply_coming_soon.text,
                ),
            )
            apply_state_transition(
                conversation_state=conversation_state,
                next_state=STATE_IDLE,
                clear_flow_data=True,
            )
            logger.info("local_job_apply_stub", user_id=user.id)
            return

        # Qualquer outra entrada: reforça as ações disponíveis (candidatar/menu).
        if job is None:
            self.send_msg(
                user,
                chat_id,
                self.resolve_message(
                    BOT_MESSAGES.local_jobs.job_unavailable.key,
                    BOT_MESSAGES.local_jobs.job_unavailable.text,
                ),
            )
            apply_state_transition(
                conversation_state=conversation_state,
                next_state=STATE_IDLE,
                clear_flow_data=True,
            )
            return

        self.send_msg(user, chat_id, self._format_job_detail(job))

    def handle(self, user: UserProfile, chat_id: str, text: str) -> bool:
        current_action = normalize_current_action(self._get_conversation_state(user).current_action)
        if current_action == STATE_LOCAL_JOBS_LIST:
            self.handle_jobs_list_selection(user, chat_id, text)
            return True
        if current_action == STATE_LOCAL_JOB_DETAIL:
            self.handle_job_detail(user, chat_id, text)
            return True
        return False
