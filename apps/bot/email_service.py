"""Servicos de email para fluxos operacionais do bot."""

import time

import structlog
from django.conf import settings as django_settings

from apps.bot.messages import BOT_MESSAGES
from apps.users.models import UserProfile
from config.env import env, settings as app_settings
from infra.email.factory import (
    EmailProviderConfigurationError,
    UnknownEmailProviderError,
    get_email_fallback_provider,
    get_email_provider,
)
from infra.email.idempotency import build_email_idempotency_key

logger = structlog.get_logger(__name__)

# E-mail de alerta operacional - configuravel via env; fallback para o remetente padrao (D-05)
ALERT_EMAIL = env("ALERT_EMAIL", default="") or env("DEFAULT_FROM_EMAIL")
ALERT_SUBJECT = BOT_MESSAGES.tasks.alert_subject_offline.text


def mask_recipient(recipient: str) -> str:
    """Mask email address for logging: j***@domain.com pattern (D-10)."""
    if "@" not in recipient:
        return "***"
    local, domain = recipient.rsplit("@", 1)
    if not local:
        return f"***@{domain}"
    return f"{local[0]}***@{domain}"


def _try_fallback(
    *,
    subject: str,
    message: str,
    from_email: str,
    recipient_list: list[str],
    idempotency_key: str | None,
    event_type: str,
    primary_provider_name: str,
    primary_error_code: str | None,
) -> dict[str, str | None]:
    """Attempt fallback send after primary failure.

    Returns the fallback result dict, or the primary error dict if fallback
    is not available.
    """
    fallback_provider_name = app_settings.email.fallback_provider

    # Log fallback trigger BEFORE attempting fallback (D-12, D-05)
    logger.info(
        "email_fallback_triggered",
        primary_provider=primary_provider_name,
        fallback_provider=fallback_provider_name,
        reason=primary_error_code,
        event_type=event_type,
    )

    fallback_provider = get_email_fallback_provider()

    if fallback_provider is None:
        # Fallback not configured or misconfigured
        logger.warning(
            "email_fallback_provider_unavailable",
            reason="config_error",
            event_type=event_type,
        )
        return {
            "status": "error",
            "provider": primary_provider_name,
            "message_id": None,
            "error_code": primary_error_code,
        }

    try:
        start = time.monotonic()
        fallback_result = fallback_provider.send(
            subject=subject,
            message=message,
            from_email=from_email,
            recipient_list=recipient_list,
            idempotency_key=idempotency_key,
        )
        elapsed = round((time.monotonic() - start) * 1000)

        if fallback_result.status == "sent":
            logger.info(
                "email_send_success",
                provider=fallback_result.provider,
                status="sent",
                message_id=fallback_result.message_id,
                event_type=event_type,
                duration_ms=elapsed,
                recipient=mask_recipient(recipient_list[0]) if recipient_list else "",
            )
        else:
            logger.error(
                "email_fallback_failed",
                primary_provider=primary_provider_name,
                fallback_provider=fallback_result.provider,
                fallback_error=fallback_result.error_code,
                event_type=event_type,
            )
        return fallback_result.to_dict()
    except Exception as exc:
        logger.error(
            "email_fallback_failed",
            primary_provider=primary_provider_name,
            fallback_provider=fallback_provider_name,
            fallback_error=exc.__class__.__name__.lower(),
            event_type=event_type,
        )
        return {
            "status": "error",
            "provider": fallback_provider_name,
            "message_id": None,
            "error_code": exc.__class__.__name__.lower(),
        }


def send_transactional_email(
    *,
    subject: str,
    message: str,
    recipient_list: list[str],
    idempotency_key: str | None = None,
    event_type: str = "transactional",
) -> dict[str, str | None]:
    fallback_configured = bool(app_settings.email.fallback_provider)

    try:
        provider = get_email_provider()
        start = time.monotonic()
        result = provider.send(
            subject=subject,
            message=message,
            from_email=django_settings.DEFAULT_FROM_EMAIL,
            recipient_list=recipient_list,
            idempotency_key=idempotency_key,
        )
        elapsed = round((time.monotonic() - start) * 1000)

        if result.status == "sent":
            logger.info(
                "email_send_success",
                provider=result.provider,
                status="sent",
                message_id=result.message_id,
                event_type=event_type,
                duration_ms=elapsed,
                recipient=mask_recipient(recipient_list[0]) if recipient_list else "",
            )
        else:
            logger.error(
                "email_send_failure",
                provider=result.provider,
                error_code=result.error_code,
                event_type=event_type,
                duration_ms=elapsed,
            )
            # Primary failed with status="error" — try fallback if configured (D-02)
            if fallback_configured:
                return _try_fallback(
                    subject=subject,
                    message=message,
                    from_email=django_settings.DEFAULT_FROM_EMAIL,
                    recipient_list=recipient_list,
                    idempotency_key=idempotency_key,
                    event_type=event_type,
                    primary_provider_name=result.provider,
                    primary_error_code=result.error_code,
                )
        return result.to_dict()
    except UnknownEmailProviderError:
        logger.error(
            "email_provider_unknown",
            error_code="unknown_provider",  # T-42-06: no raw str(exc) which may contain PII
            event_type=event_type,
        )
        primary_provider_name = getattr(django_settings, "EMAIL_PROVIDER", "unknown")
        primary_error_code = "unknown_provider"

        if fallback_configured:
            return _try_fallback(
                subject=subject,
                message=message,
                from_email=django_settings.DEFAULT_FROM_EMAIL,
                recipient_list=recipient_list,
                idempotency_key=idempotency_key,
                event_type=event_type,
                primary_provider_name=primary_provider_name,
                primary_error_code=primary_error_code,
            )

        return {
            "status": "error",
            "provider": primary_provider_name,
            "message_id": None,
            "error_code": primary_error_code,
        }
    except EmailProviderConfigurationError:
        logger.error(
            "email_provider_configuration_error",
            error_code="provider_misconfigured",  # T-42-06: no raw str(exc) which may contain PII
            event_type=event_type,
        )
        primary_provider_name = getattr(django_settings, "EMAIL_PROVIDER", "unknown")
        primary_error_code = "provider_misconfigured"

        if fallback_configured:
            return _try_fallback(
                subject=subject,
                message=message,
                from_email=django_settings.DEFAULT_FROM_EMAIL,
                recipient_list=recipient_list,
                idempotency_key=idempotency_key,
                event_type=event_type,
                primary_provider_name=primary_provider_name,
                primary_error_code=primary_error_code,
            )

        return {
            "status": "error",
            "provider": primary_provider_name,
            "message_id": None,
            "error_code": primary_error_code,
        }
    except Exception as exc:
        logger.error(
            "email_provider_send_failed",
            error_code=exc.__class__.__name__.lower(),  # T-42-06: no raw str(exc) which may contain PII
            event_type=event_type,
        )
        primary_provider_name = getattr(django_settings, "EMAIL_PROVIDER", "unknown")
        primary_error_code = exc.__class__.__name__.lower()

        if fallback_configured:
            return _try_fallback(
                subject=subject,
                message=message,
                from_email=django_settings.DEFAULT_FROM_EMAIL,
                recipient_list=recipient_list,
                idempotency_key=idempotency_key,
                event_type=event_type,
                primary_provider_name=primary_provider_name,
                primary_error_code=primary_error_code,
            )

        return {
            "status": "error",
            "provider": primary_provider_name,
            "message_id": None,
            "error_code": primary_error_code,
        }


def send_offline_alert_email(
    session_name: str,
    current_status: str,
    error_message: str | None = None,
    reconnect_attempted: bool = False,
    reconnect_success: bool = False,
) -> None:
    """Envia alerta de indisponibilidade do bot para o administrador."""
    body_lines = [
        BOT_MESSAGES.tasks.alert_offline_intro.text.format(session_name=session_name),
        "",
        BOT_MESSAGES.tasks.alert_status_line.text.format(current_status=current_status),
    ]

    if error_message:
        body_lines.append(
            BOT_MESSAGES.tasks.alert_error_line.text.format(error_message=error_message)
        )

    if reconnect_attempted:
        reconnect_result = (
            "Reconexao bem-sucedida" if reconnect_success else "Reconexao falhou apos 3 tentativas"
        )
        body_lines.append(
            BOT_MESSAGES.tasks.alert_reconnect_line.text.format(reconnect_result=reconnect_result)
        )

    body_lines.extend(
        [
            "",
            "Verifique o painel administrativo para mais detalhes:",
            f"{getattr(django_settings, 'PORTAL_BASE_URL', 'http://localhost:8000')}/admin/bot/bothealthcheck/",
        ]
    )

    result = send_transactional_email(
        subject=ALERT_SUBJECT,
        message="\n".join(body_lines),
        recipient_list=[ALERT_EMAIL],
        event_type="offline_alert",
    )

    if result["status"] != "sent":
        logger.warning(
            "offline_alert_email_failed",
            provider=result.get("provider"),
            error_code=result.get("error_code"),
            session_name=session_name,
        )


def send_confirmation_email_to_user(user_id: int) -> dict:
    """Envia e-mail de confirmacao para um usuario, com retries tratados na task."""
    try:
        user = UserProfile.objects.get(id=user_id)
    except UserProfile.DoesNotExist:
        return {"status": "error", "reason": "user_not_found", "user_id": user_id}

    if user.email_verified:
        return {"status": "skipped", "reason": "already_verified", "user_id": user_id}

    if not user.email_confirmation_token:
        return {"status": "error", "reason": "no_token", "user_id": user_id}

    if not user.email:
        return {"status": "error", "reason": "no_email", "user_id": user_id}

    # PORTAL_BASE_URL e obrigatoria em producao (validada em production.py).
    # Em dev/testes usamos localhost como fallback quando nao configurada.
    base_url = (getattr(django_settings, "PORTAL_BASE_URL", "") or "http://localhost:8000").rstrip(
        "/"
    )
    confirm_url = f"{base_url}/confirmar-email/{user.email_confirmation_token}"

    body_lines = [
        BOT_MESSAGES.tasks.confirm_email_greeting.text.format(ra=user.ra or "aluno"),
        "",
        "Voce solicitou acesso ao IterBot, o assistente de vagas da UTFPR.",
        "",
        f"Seu RA: {user.ra}",
        "",
        "Para confirmar seu e-mail e ativar o acesso, clique no link abaixo:",
        "",
        confirm_url,
        "",
        "Este link expira em 24 horas.",
        "",
        "Se voce nao solicitou este acesso, ignore este e-mail.",
        "",
        "Atenciosamente,",
        "Equipe IterBot UTFPR",
    ]
    idempotency_key = build_email_idempotency_key(
        "email_confirmation",
        recipient=user.email,
        event_token=user.email_confirmation_token,
        event_uid=str(user.id),
    )

    result = send_transactional_email(
        subject=BOT_MESSAGES.tasks.confirm_email_subject.text,
        message="\n".join(body_lines),
        recipient_list=[user.email],
        idempotency_key=idempotency_key,
        event_type="email_confirmation",
    )

    if result["status"] != "sent":
        return {
            "status": "error",
            "reason": "provider_error",
            "provider": result.get("provider"),
            "error_code": result.get("error_code"),
            "user_id": user_id,
        }

    return {
        "status": "sent",
        "provider": result.get("provider"),
        "message_id": result.get("message_id"),
        "user_id": user_id,
        "email": user.email,
    }


def send_company_confirmation_email_to_user(user_id: int) -> dict:
    """Envia e-mail de confirmação de vínculo empresa→WhatsApp."""
    try:
        user = UserProfile.objects.select_related("company").get(id=user_id)
    except UserProfile.DoesNotExist:
        return {"status": "error", "reason": "user_not_found", "user_id": user_id}

    if user.is_company_authenticated:
        return {"status": "skipped", "reason": "already_authenticated", "user_id": user_id}

    if not user.company_confirmation_token:
        return {"status": "error", "reason": "no_token", "user_id": user_id}

    if user.company is None:
        return {"status": "error", "reason": "no_company", "user_id": user_id}

    base_url = (getattr(django_settings, "PORTAL_BASE_URL", "") or "http://localhost:8000").rstrip(
        "/"
    )
    confirm_url = f"{base_url}/accounts/confirmar-empresa/{user.company_confirmation_token}/"

    company_email = user.company.email
    company_name = user.company.nome

    body_lines = [
        f"Olá, {company_name}!",
        "",
        "Recebemos uma solicitação para vincular este e-mail ao IterBot via WhatsApp.",
        "",
        "Para confirmar o vínculo e acessar o menu da empresa no bot, clique no link abaixo:",
        "",
        confirm_url,
        "",
        "Este link expira em 24 horas.",
        "",
        "Se você não solicitou este acesso, ignore este e-mail.",
        "",
        "Atenciosamente,",
        "Equipe IterBot UTFPR",
    ]
    idempotency_key = build_email_idempotency_key(
        "company_confirmation",
        recipient=company_email,
        event_token=user.company_confirmation_token,
        event_uid=str(user.id),
    )

    result = send_transactional_email(
        subject="IterBot — Confirme o vínculo da sua empresa",
        message="\n".join(body_lines),
        recipient_list=[company_email],
        idempotency_key=idempotency_key,
        event_type="company_confirmation",
    )

    if result["status"] != "sent":
        return {
            "status": "error",
            "reason": "provider_error",
            "provider": result.get("provider"),
            "error_code": result.get("error_code"),
            "user_id": user_id,
        }

    return {
        "status": "sent",
        "provider": result.get("provider"),
        "message_id": result.get("message_id"),
        "user_id": user_id,
        "email": company_email,
    }


def send_job_application_email_to_company(application_id: int) -> dict:
    """Notifica a empresa por e-mail sobre uma nova candidatura.

    Inclui os dados de contato do aluno e o mini-perfil congelado em
    `profile_snapshot`. Idempotente por candidatura (a chave é o id da
    `JobApplication`), então retries do Celery não duplicam o envio.
    """
    from apps.jobs.models import JobApplication

    try:
        application = JobApplication.objects.select_related("user", "job", "job__company").get(
            id=application_id
        )
    except JobApplication.DoesNotExist:
        return {
            "status": "error",
            "reason": "application_not_found",
            "application_id": application_id,
        }

    job = application.job
    company = job.company
    student = application.user
    snapshot = application.profile_snapshot or {}

    if not company.email:
        return {"status": "error", "reason": "no_company_email", "application_id": application_id}

    link = snapshot.get("linkedin_url") or snapshot.get("cv_url") or "Não informado"

    body_lines = [
        f"Olá, {company.nome}!",
        "",
        f"Você recebeu uma nova candidatura para a vaga: {job.titulo}",
        "",
        "Dados do candidato:",
        f"- RA: {student.ra or 'Não informado'}",
        f"- E-mail: {student.email or 'Não informado'}",
        f"- WhatsApp: {student.phone_number}",
        "",
        "Mini-perfil:",
        f"- Período: {snapshot.get('periodo') or 'Não informado'}",
        f"- Habilidades: {snapshot.get('skills') or 'Não informado'}",
        f"- Link: {link}",
    ]
    if application.message:
        body_lines += ["", f"Recado do candidato: {application.message}"]
    body_lines += [
        "",
        "Acompanhe e atualize o status desta candidatura no portal:",
        (getattr(django_settings, "PORTAL_BASE_URL", "") or "http://localhost:8000").rstrip("/")
        + "/empresas/candidaturas/",
        "",
        "Atenciosamente,",
        "Equipe IterBot UTFPR",
    ]

    idempotency_key = build_email_idempotency_key(
        "job_application",
        recipient=company.email,
        event_token=str(application.id),
        event_uid=str(application.id),
    )

    result = send_transactional_email(
        subject=f"IterBot — Nova candidatura para {job.titulo}",
        message="\n".join(body_lines),
        recipient_list=[company.email],
        idempotency_key=idempotency_key,
        event_type="job_application",
    )

    if result["status"] != "sent":
        return {
            "status": "error",
            "reason": "provider_error",
            "provider": result.get("provider"),
            "error_code": result.get("error_code"),
            "application_id": application_id,
        }

    return {
        "status": "sent",
        "provider": result.get("provider"),
        "message_id": result.get("message_id"),
        "application_id": application_id,
    }
