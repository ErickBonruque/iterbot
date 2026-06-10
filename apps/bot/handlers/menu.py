"""Menu handler for displaying navigation options."""

import structlog

from apps.bot.messages import BOT_MESSAGES
from apps.core.portal_links import build_portal_url
from apps.users.models import UserProfile
from infra.waha.protocols import MessageSender

from .base import BaseHandler

logger = structlog.get_logger(__name__)


class MenuHandler(BaseHandler):
    """Handles menu display and navigation."""

    def __init__(self, waha_client: MessageSender) -> None:
        super().__init__(waha_client)

    def send_menu(self, user: UserProfile, chat_id: str) -> None:
        # Recarrega para garantir flags atualizados após confirmação web.
        from apps.users.models import UserProfile

        fresh = UserProfile.objects.select_related("company").get(pk=user.pk)

        if fresh.is_company_authenticated:
            self._send_company_main_menu(fresh, chat_id)
            return

        if fresh.is_authenticated_utfpr:
            switch_empresa = (
                "\n5️⃣ Mudar para conta empresa"
                if fresh.is_company_authenticated is False and fresh.company is not None
                else ""
            )
            menu_text = self.resolve_message(
                BOT_MESSAGES.menu.main_authenticated.key,
                BOT_MESSAGES.menu.main_authenticated.text,
                brand_header=BOT_MESSAGES.menu.brand_header,
                ra=fresh.ra or "Não cadastrado",
                switch_empresa=switch_empresa,
            )
        else:
            menu_text = self.resolve_message(
                BOT_MESSAGES.menu.main_unauthenticated.key,
                BOT_MESSAGES.menu.main_unauthenticated.text,
                brand_header=BOT_MESSAGES.menu.brand_header,
            )

        self.send_msg(user, chat_id, menu_text)
        logger.info(
            "menu_displayed",
            user_id=user.id,
            authenticated=fresh.is_authenticated_utfpr,
            company_auth=fresh.is_company_authenticated,
        )

    def _send_company_main_menu(self, user: UserProfile, chat_id: str) -> None:
        company_name = user.company.nome if user.company else "Empresa"
        switch_aluno = (
            "\n🔄 Digitar *aluno* para trocar para conta de aluno"
            if user.is_authenticated_utfpr
            else ""
        )
        menu_text = self.resolve_message(
            BOT_MESSAGES.menu.company_main.key,
            BOT_MESSAGES.menu.company_main.text,
            brand_header=BOT_MESSAGES.menu.brand_header,
            company_name=company_name,
            switch_aluno=switch_aluno,
        )
        self.send_msg(user, chat_id, menu_text)
        logger.info(
            "company_menu_displayed", user_id=user.id, company_id=getattr(user.company, "id", None)
        )

    def send_company_jobs(self, user: UserProfile, chat_id: str) -> None:
        """Lista vagas cadastradas da empresa (leitura)."""
        from apps.jobs.models.job import Job

        if user.company is None:
            self.send_unknown_command(user, chat_id)
            return

        jobs = list(
            Job.objects.filter(company=user.company)
            .exclude(status="removed")
            .order_by("-created_at")[:20]
        )

        if not jobs:
            msg = self.resolve_message(
                BOT_MESSAGES.menu.company_jobs_empty.key,
                BOT_MESSAGES.menu.company_jobs_empty.text,
            )
            self.send_msg(user, chat_id, msg)
            return

        status_labels = {
            "pending": "Aguardando",
            "approved": "Aprovada",
            "expired": "Expirada",
            "draft": "Rascunho",
            "removed": "Removida",
        }
        items = []
        for job in jobs:
            status_label = status_labels.get(job.status, job.status)
            item = self.resolve_message(
                BOT_MESSAGES.menu.company_job_item.key,
                BOT_MESSAGES.menu.company_job_item.text,
                titulo=job.titulo,
                tipo=job.tipo.upper(),
                status=status_label,
            )
            items.append(item)

        msg = self.resolve_message(
            BOT_MESSAGES.menu.company_jobs_header.key,
            BOT_MESSAGES.menu.company_jobs_header.text,
            company_name=user.company.nome,
            jobs_list="\n".join(items),
            count=len(jobs),
        )
        self.send_msg(user, chat_id, msg)

    def send_company_portal_link(
        self, user: UserProfile, chat_id: str, portal_base_url: str
    ) -> None:
        profile_url = build_portal_url(portal_base_url, "/empresas/perfil/")
        if profile_url is None:
            self.send_msg(user, chat_id, "❌ Portal indisponível no momento.")
            return
        msg = self.resolve_message(
            BOT_MESSAGES.menu.company_portal_link.key,
            BOT_MESSAGES.menu.company_portal_link.text,
            profile_url=profile_url,
        )
        self.send_msg(user, chat_id, msg)

    def send_company_new_job_link(
        self, user: UserProfile, chat_id: str, portal_base_url: str
    ) -> None:
        new_job_url = build_portal_url(portal_base_url, "/empresas/vagas/nova/")
        if new_job_url is None:
            self.send_msg(user, chat_id, "❌ Portal indisponível no momento.")
            return
        msg = self.resolve_message(
            BOT_MESSAGES.menu.company_new_job_link.key,
            BOT_MESSAGES.menu.company_new_job_link.text,
            new_job_url=new_job_url,
        )
        self.send_msg(user, chat_id, msg)

    def send_company_onboarding_menu(self, user: UserProfile, chat_id: str) -> None:
        menu_text = self.resolve_message(
            BOT_MESSAGES.menu.company_onboarding_menu.key,
            BOT_MESSAGES.menu.company_onboarding_menu.text,
            brand_header=BOT_MESSAGES.menu.brand_header,
        )
        self.send_msg(user, chat_id, menu_text)

    def send_company_onboarding_signup_link(
        self,
        user: UserProfile,
        chat_id: str,
        portal_base_url: str,
    ) -> bool:
        signup_url = build_portal_url(portal_base_url, "/empresas/signup/")
        if signup_url is None:
            return False
        msg = self.resolve_message(
            BOT_MESSAGES.menu.company_onboarding_signup.key,
            BOT_MESSAGES.menu.company_onboarding_signup.text,
            signup_url=signup_url,
        )
        self.send_msg(user, chat_id, msg)
        return True

    def send_unknown_command(self, user: UserProfile, chat_id: str) -> None:
        msg = self.resolve_message(
            BOT_MESSAGES.menu.unknown_command.key,
            BOT_MESSAGES.menu.unknown_command.text,
        )
        self.send_msg(user, chat_id, msg)
        logger.debug("unknown_command_sent", user_id=user.id)

    def handle(self, user: UserProfile, chat_id: str, text: str) -> bool:
        return False
