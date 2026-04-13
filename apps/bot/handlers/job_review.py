"""Handler para consulta sob demanda de review de vagas (opcao 4 do menu)."""

import structlog

from apps.users.models import UserProfile
from infra.jobspy.service import JobSearchService

from .base import BaseHandler

logger = structlog.get_logger(__name__)


class JobReviewHandler(BaseHandler):
    """Envia review de vagas sob demanda para o aluno."""

    def __init__(self, waha_client, job_service: JobSearchService | None = None) -> None:
        super().__init__(waha_client)
        self.job_service = job_service or JobSearchService()

    def send_review(self, user: UserProfile, chat_id: str) -> None:
        # Importacao lazy para evitar circular import com apps.jobs.tasks.
        from apps.jobs.tasks import _build_review_for_user, _format_review_message

        if not user.selected_course:
            self.send_msg(
                user,
                chat_id,
                "⚠️ Você não tem curso definido.\n\n"
                "Use a opção *3 - Buscar Vagas* para selecionar seu curso primeiro.",
            )
            logger.info("review_requested_no_course", user_id=user.id)
            return

        self.send_msg(user, chat_id, "🔎 Buscando vagas para você... Aguarde um momento.")

        try:
            jobs = _build_review_for_user(user.selected_course, self.job_service)
        except Exception as exc:
            logger.error(
                "review_on_demand_failed",
                user_id=user.id,
                course=user.selected_course.name,
                error=str(exc),
                exc_info=True,
            )
            self.send_msg(
                user,
                chat_id,
                "❌ Ocorreu um erro ao buscar vagas. Tente novamente mais tarde.",
            )
            return

        if not jobs:
            self.send_msg(
                user,
                chat_id,
                "😔 Não encontrei vagas para o seu curso no momento.\n\n"
                "_Tente novamente em alguns dias ou use a opção *3 - Buscar Vagas* para busca manual._",
            )
            logger.info(
                "review_on_demand_no_jobs",
                user_id=user.id,
                course=user.selected_course.name,
            )
            return

        msg = _format_review_message(user.selected_course.name, jobs)
        self.send_msg(user, chat_id, msg)
        logger.info(
            "review_on_demand_sent",
            user_id=user.id,
            course=user.selected_course.name,
            jobs_count=len(jobs),
        )

    def handle(self, user: UserProfile, chat_id: str, text: str) -> bool:
        return False
