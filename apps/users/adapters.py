"""Adapter do django-allauth integrado ao provider transacional unificado.

Todo e-mail disparado pelo allauth (signup confirmation, email_confirmation,
password_reset_key, etc.) passa por `send_transactional_email`, garantindo que
o provider configurado em `EMAIL_PROVIDER` (Brevo por padrao) seja usado e o
Django `EMAIL_BACKEND` nao precise apontar para SES/SMTP reais.
"""

from __future__ import annotations

import structlog
from allauth.account.adapter import DefaultAccountAdapter

from apps.bot.email_service import send_transactional_email
from apps.users.validators import validate_utfpr_email
from infra.email.idempotency import build_email_idempotency_key

logger = structlog.get_logger(__name__)

# Mapa template_prefix -> (idempotency_namespace, event_type).
# Novos templates podem ser acrescentados aqui quando o allauth expuser outros fluxos.
_ALLAUTH_TEMPLATE_MAP: dict[str, tuple[str, str]] = {
    "account/email/password_reset_key": ("password_reset", "password_reset"),
    "account/email/email_confirmation_signup": ("email_confirmation_signup", "email_confirmation"),
    "account/email/email_confirmation": ("email_confirmation_resend", "email_confirmation"),
}
_DEFAULT_NAMESPACE = "allauth_generic"
_DEFAULT_EVENT_TYPE = "allauth_generic"


class UTFPRAccountAdapter(DefaultAccountAdapter):
    """Adapter customizado do django-allauth.

    - Rotas de alunos (/accounts/): exige dominio `@alunos.utfpr.edu.br`.
    - Rotas de empresas (/empresas/): aceita qualquer e-mail.
    - Todos os e-mails do allauth sao encaminhados ao provider transacional
      configurado em `EMAIL_PROVIDER` (Brevo, SES, Resend, etc.).
    """

    def clean_email(self, email):
        """Valida e-mail conforme a rota de origem da request."""
        email = super().clean_email(email)
        if hasattr(self, "request") and self.request and self.request.path.startswith("/empresas/"):
            return email
        validate_utfpr_email(email)
        return email

    def send_mail(self, template_prefix, email, context):
        """Renderiza o template do allauth e envia via provider transacional.

        O retorno preserva o dict padrao de `send_transactional_email` para que
        o allauth (que ignora o retorno) nao seja afetado, enquanto o log
        estruturado capture sucesso/erro. Em caso de falha o erro e logado mas
        nao propaga excecao para nao quebrar o fluxo do allauth (mensagens
        genericas sao preservadas — o usuario percebera a ausencia do e-mail,
        mas a pagina nao retorna 500).
        """
        message = self.render_mail(template_prefix, email, context)
        namespace, event_type = _ALLAUTH_TEMPLATE_MAP.get(
            template_prefix, (_DEFAULT_NAMESPACE, _DEFAULT_EVENT_TYPE)
        )
        user = context.get("user") if isinstance(context, dict) else None
        event_uid = str(user.pk) if user is not None and getattr(user, "pk", None) else email
        event_token = ""
        if isinstance(context, dict):
            event_token = str(context.get("key") or context.get("token") or "")

        idempotency_key = build_email_idempotency_key(
            namespace,
            recipient=email,
            event_token=event_token,
            event_uid=event_uid,
        )
        result = send_transactional_email(
            subject=message.subject,
            message=message.body,
            recipient_list=[email],
            idempotency_key=idempotency_key,
            event_type=event_type,
        )
        if result.get("status") != "sent":
            logger.error(
                "allauth_email_send_failed",
                template_prefix=template_prefix,
                provider=result.get("provider"),
                error_code=result.get("error_code"),
                event_type=event_type,
            )
        return result
