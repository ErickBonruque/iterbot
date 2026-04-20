
from allauth.account.adapter import DefaultAccountAdapter

from apps.bot.email_service import send_transactional_email
from apps.users.validators import validate_utfpr_email
from infra.email.idempotency import build_email_idempotency_key


class UTFPRAccountAdapter(DefaultAccountAdapter):
    """
    Adapter customizado do django-allauth para validar dominio de e-mail.
    - Rotas de alunos (/accounts/): restringe a @alunos.utfpr.edu.br
    - Rotas de empresas (/empresas/): permite qualquer e-mail
    """

    def clean_email(self, email):
        """
        Valida e-mail condicionalmente baseado na rota de origem.
        """
        email = super().clean_email(email)
        # Rotas de empresa nao tem restricao de dominio
        if hasattr(self, "request") and self.request and self.request.path.startswith("/empresas/"):
            return email
        validate_utfpr_email(email)
        return email

    def send_mail(self, template_prefix, email, context):
        if template_prefix != "account/email/password_reset_key":
            return super().send_mail(template_prefix, email, context)

        message = super().render_mail(template_prefix, email, context)
        idempotency_key = build_email_idempotency_key(
            "password_reset",
            recipient=email,
            event_token=context.get("key"),
            event_uid=context.get("uid"),
        )
        return send_transactional_email(
            subject=message.subject,
            message=message.body,
            recipient_list=[email],
            idempotency_key=idempotency_key,
        )
