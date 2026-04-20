"""Servicos de email para fluxos operacionais do bot."""

from django.conf import settings as django_settings
from django.core.mail import send_mail

from apps.bot.messages import BOT_MESSAGES
from apps.users.models import UserProfile

# E-mail de alerta fixo — nao configuravel via admin neste milestone (D-05)
ALERT_EMAIL = "bonrqueruck@gmail.com"
ALERT_SUBJECT = BOT_MESSAGES.tasks.alert_subject_offline.text


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
            "Reconexao bem-sucedida"
            if reconnect_success
            else "Reconexao falhou apos 3 tentativas"
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

    send_mail(
        subject=ALERT_SUBJECT,
        message="\n".join(body_lines),
        from_email=django_settings.DEFAULT_FROM_EMAIL,
        recipient_list=[ALERT_EMAIL],
        fail_silently=True,
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

    base_url = getattr(django_settings, "PORTAL_BASE_URL", "https://3-86-57-105.sslip.io")
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

    send_mail(
        subject=BOT_MESSAGES.tasks.confirm_email_subject.text,
        message="\n".join(body_lines),
        from_email=django_settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        fail_silently=False,
    )

    return {"status": "sent", "user_id": user_id, "email": user.email}
