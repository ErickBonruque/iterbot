"""Handler de candidatura a vagas locais com coleta de mini-perfil (Fase 4).

Fluxo: a partir do detalhe da vaga (Fase 3), o aluno digita *candidatar*.
- Se ainda não tem mini-perfil completo → coleta período → skills → link.
- Se já tem → pula direto para a confirmação.
Ao confirmar, cria a `JobApplication` com um snapshot do perfil e notifica a
empresa por e-mail (degradação graciosa: o e-mail nunca derruba o fluxo).
"""

import structlog
from django.core.exceptions import ValidationError
from django.core.validators import URLValidator
from django.db import IntegrityError

from apps.bot.messages import BOT_MESSAGES
from apps.bot.models import ConversationState
from apps.bot.state_machine import (
    STATE_CONFIRM_APPLICATION,
    STATE_IDLE,
    STATE_PROFILE_LINK,
    STATE_PROFILE_PERIODO,
    STATE_PROFILE_SKILLS,
    apply_state_transition,
    normalize_current_action,
)
from apps.bot.tasks import send_job_application_email
from apps.jobs.models import Job, JobApplication, JobStatus
from apps.users.models import StudentProfile, UserProfile
from infra.waha.protocols import MessageSender

from .base import BaseHandler

logger = structlog.get_logger(__name__)

_CONFIRM_WORDS = frozenset({"confirmar", "sim", "ok", "confirmo"})
_SKIP_WORDS = frozenset({"pular", "nao", "não", "skip"})


class ApplicationHandler(BaseHandler):
    """Coleta o mini-perfil e registra a candidatura do aluno."""

    def __init__(self, waha_client: MessageSender) -> None:
        super().__init__(waha_client)

    def _get_conversation_state(self, user: UserProfile) -> ConversationState:
        conversation_state, _ = ConversationState.objects.get_or_create(user=user)
        return conversation_state

    # --- Entrada do fluxo -----------------------------------------------------

    def start_application(self, user: UserProfile, chat_id: str, job: Job) -> None:
        """Inicia a candidatura para `job` (chamado pelo LocalJobsHandler)."""
        if JobApplication.objects.filter(user=user, job=job).exists():
            self.send_msg(
                user,
                chat_id,
                self.resolve_message(
                    BOT_MESSAGES.application.already_applied.key,
                    BOT_MESSAGES.application.already_applied.text,
                ),
            )
            apply_state_transition(
                conversation_state=self._get_conversation_state(user),
                next_state=STATE_IDLE,
                clear_flow_data=True,
            )
            logger.info("application_duplicate_blocked", user_id=user.id, job_id=job.id)
            return

        conversation_state = self._get_conversation_state(user)
        conversation_state.flow_data["application_job_id"] = job.id

        profile = getattr(user, "student_profile", None)
        if profile is not None and profile.is_complete:
            # Reutiliza o mini-perfil já cadastrado — pula a coleta.
            conversation_state.flow_data["profile_periodo"] = profile.periodo
            conversation_state.flow_data["profile_skills"] = profile.skills
            conversation_state.flow_data["profile_link"] = (
                profile.linkedin_url or profile.cv_url or ""
            )
            apply_state_transition(
                conversation_state=conversation_state,
                next_state=STATE_CONFIRM_APPLICATION,
                update_fields=["flow_data"],
            )
            self._send_confirmation(user, chat_id, job)
            logger.info("application_profile_reused", user_id=user.id, job_id=job.id)
            return

        apply_state_transition(
            conversation_state=conversation_state,
            next_state=STATE_PROFILE_PERIODO,
            update_fields=["flow_data"],
        )
        self.send_msg(
            user,
            chat_id,
            self.resolve_message(
                BOT_MESSAGES.application.prompt_periodo.key,
                BOT_MESSAGES.application.prompt_periodo.text,
            ),
        )
        logger.info("application_profile_collection_started", user_id=user.id, job_id=job.id)

    # --- Coleta de perfil -----------------------------------------------------

    def _handle_periodo(self, user: UserProfile, chat_id: str, text: str) -> None:
        value = text.strip()
        if not value:
            self._send_invalid_field(user, chat_id)
            return
        conversation_state = self._get_conversation_state(user)
        conversation_state.flow_data["profile_periodo"] = value
        apply_state_transition(
            conversation_state=conversation_state,
            next_state=STATE_PROFILE_SKILLS,
            update_fields=["flow_data"],
        )
        self.send_msg(
            user,
            chat_id,
            self.resolve_message(
                BOT_MESSAGES.application.prompt_skills.key,
                BOT_MESSAGES.application.prompt_skills.text,
            ),
        )

    def _handle_skills(self, user: UserProfile, chat_id: str, text: str) -> None:
        value = text.strip()
        if not value:
            self._send_invalid_field(user, chat_id)
            return
        conversation_state = self._get_conversation_state(user)
        conversation_state.flow_data["profile_skills"] = value
        apply_state_transition(
            conversation_state=conversation_state,
            next_state=STATE_PROFILE_LINK,
            update_fields=["flow_data"],
        )
        self.send_msg(
            user,
            chat_id,
            self.resolve_message(
                BOT_MESSAGES.application.prompt_link.key,
                BOT_MESSAGES.application.prompt_link.text,
            ),
        )

    def _handle_link(self, user: UserProfile, chat_id: str, text: str) -> None:
        value = text.strip()
        link = ""
        if value.lower() not in _SKIP_WORDS:
            try:
                URLValidator()(value)
            except ValidationError:
                self.send_msg(
                    user,
                    chat_id,
                    self.resolve_message(
                        BOT_MESSAGES.application.invalid_link.key,
                        BOT_MESSAGES.application.invalid_link.text,
                    ),
                )
                return
            link = value

        conversation_state = self._get_conversation_state(user)
        conversation_state.flow_data["profile_link"] = link
        apply_state_transition(
            conversation_state=conversation_state,
            next_state=STATE_CONFIRM_APPLICATION,
            update_fields=["flow_data"],
        )
        job = self._resolve_job(conversation_state)
        if job is None:
            self._send_job_unavailable(user, chat_id)
            return
        self._send_confirmation(user, chat_id, job)

    # --- Confirmação e finalização -------------------------------------------

    def _handle_confirmation(self, user: UserProfile, chat_id: str, text: str) -> None:
        if text.strip().lower() not in _CONFIRM_WORDS:
            conversation_state = self._get_conversation_state(user)
            job = self._resolve_job(conversation_state)
            if job is None:
                self._send_job_unavailable(user, chat_id)
                return
            self._send_confirmation(user, chat_id, job)
            return
        self._finalize(user, chat_id)

    def _finalize(self, user: UserProfile, chat_id: str) -> None:
        conversation_state = self._get_conversation_state(user)
        flow = conversation_state.flow_data
        job = self._resolve_job(conversation_state)
        if job is None:
            self._send_job_unavailable(user, chat_id)
            return

        periodo = flow.get("profile_periodo", "")
        skills = flow.get("profile_skills", "")
        link = flow.get("profile_link", "")

        profile = self._save_profile(user, periodo=periodo, skills=skills, link=link)

        try:
            application = JobApplication.objects.create(
                user=user,
                job=job,
                profile_snapshot=profile.to_snapshot(),
            )
        except IntegrityError:
            # Corrida: candidatura criada em paralelo. Trata como duplicata.
            self.send_msg(
                user,
                chat_id,
                self.resolve_message(
                    BOT_MESSAGES.application.already_applied.key,
                    BOT_MESSAGES.application.already_applied.text,
                ),
            )
            apply_state_transition(
                conversation_state=conversation_state,
                next_state=STATE_IDLE,
                clear_flow_data=True,
            )
            return

        self._dispatch_company_email(application.id)

        apply_state_transition(
            conversation_state=conversation_state,
            next_state=STATE_IDLE,
            clear_flow_data=True,
        )
        self.send_msg(
            user,
            chat_id,
            self.resolve_message(
                BOT_MESSAGES.application.success.key,
                BOT_MESSAGES.application.success.text,
                company=job.company.nome,
                titulo=job.titulo,
            ),
        )
        logger.info(
            "application_created",
            user_id=user.id,
            job_id=job.id,
            application_id=application.id,
        )

    def _save_profile(
        self, user: UserProfile, *, periodo: str, skills: str, link: str
    ) -> StudentProfile:
        profile, _ = StudentProfile.objects.get_or_create(user=user)
        profile.periodo = periodo
        profile.skills = skills
        if link:
            if "linkedin" in link.lower():
                profile.linkedin_url = link
            else:
                profile.cv_url = link
        profile.save()
        return profile

    def _dispatch_company_email(self, application_id: int) -> None:
        """Dispara o e-mail à empresa. Falha de broker não derruba o fluxo."""
        try:
            send_job_application_email.delay(application_id)
        except Exception as exc:
            logger.error(
                "application_email_dispatch_failed",
                application_id=application_id,
                error=str(exc),
            )

    # --- Helpers --------------------------------------------------------------

    def _resolve_job(self, conversation_state: ConversationState) -> Job | None:
        job_id = conversation_state.flow_data.get("application_job_id")
        if not job_id:
            return None
        return (
            Job.objects.select_related("company")
            .filter(pk=job_id, status=JobStatus.APPROVED)
            .first()
        )

    def _send_confirmation(self, user: UserProfile, chat_id: str, job: Job) -> None:
        flow = self._get_conversation_state(user).flow_data
        self.send_msg(
            user,
            chat_id,
            self.resolve_message(
                BOT_MESSAGES.application.confirm.key,
                BOT_MESSAGES.application.confirm.text,
                titulo=job.titulo,
                company=job.company.nome,
                periodo=flow.get("profile_periodo", "—"),
                skills=flow.get("profile_skills", "—"),
                link=flow.get("profile_link") or "Não informado",
            ),
        )

    def _send_invalid_field(self, user: UserProfile, chat_id: str) -> None:
        self.send_msg(
            user,
            chat_id,
            self.resolve_message(
                BOT_MESSAGES.application.invalid_field.key,
                BOT_MESSAGES.application.invalid_field.text,
            ),
        )

    def _send_job_unavailable(self, user: UserProfile, chat_id: str) -> None:
        self.send_msg(
            user,
            chat_id,
            self.resolve_message(
                BOT_MESSAGES.application.job_unavailable.key,
                BOT_MESSAGES.application.job_unavailable.text,
            ),
        )
        apply_state_transition(
            conversation_state=self._get_conversation_state(user),
            next_state=STATE_IDLE,
            clear_flow_data=True,
        )

    def handle(
        self, user: UserProfile, chat_id: str, text: str, raw_text: str | None = None
    ) -> bool:
        # Campos livres do mini-perfil preservam a grafia original (raw_text);
        # confirmação/skip casam por texto normalizado.
        field_text = raw_text if raw_text is not None else text
        current_action = normalize_current_action(self._get_conversation_state(user).current_action)
        if current_action == STATE_PROFILE_PERIODO:
            self._handle_periodo(user, chat_id, field_text)
            return True
        if current_action == STATE_PROFILE_SKILLS:
            self._handle_skills(user, chat_id, field_text)
            return True
        if current_action == STATE_PROFILE_LINK:
            self._handle_link(user, chat_id, field_text)
            return True
        if current_action == STATE_CONFIRM_APPLICATION:
            self._handle_confirmation(user, chat_id, text)
            return True
        return False
