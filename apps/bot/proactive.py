"""Abstração centralizada para mensagens proativas via WhatsApp.

Todas as notificações disparadas por eventos do sistema (confirmação de
e-mail, aprovação de empresa, etc.) devem passar por ProactiveNotifier.
Isso garante um único ponto de manutenção para logging, retry e formatação.
"""

import structlog

logger = structlog.get_logger(__name__)


class ProactiveNotifier:
    """Envia mensagens proativas no WhatsApp disparadas por eventos do sistema."""

    def _get_client(self):
        from apps.bot.models import BotConfiguration
        from infra.waha.client import WahaClient

        return WahaClient(settings=BotConfiguration.get_active())

    def _reset_state(self, profile) -> None:
        from apps.bot.models import ConversationState
        from apps.bot.state_machine import STATE_IDLE, apply_state_transition

        conv, _ = ConversationState.objects.get_or_create(user=profile)
        apply_state_transition(conversation_state=conv, next_state=STATE_IDLE, clear_flow_data=True)

    def notify_student_email_confirmed(self, profile_id: int) -> dict:
        """Notifica aluno via WhatsApp após confirmação de e-mail institucional."""
        from apps.users.models import UserProfile

        profile = UserProfile.objects.get(pk=profile_id)
        if not profile.is_authenticated_utfpr or not profile.email_verified:
            return {"status": "skipped", "reason": "not_confirmed"}

        self._reset_state(profile)

        client = self._get_client()
        client.send_message(
            profile.phone_number,
            f"✅ *E-mail confirmado!*\n\n"
            f"Seu e-mail `{profile.email}` foi verificado com sucesso.\n\n"
            f"Agora você tem acesso completo ao IterBot.\n\n"
            f"Digite *menu* para ver as opções disponíveis.",
        )
        logger.info("student_email_confirmed_notified", profile_id=profile_id)
        return {"status": "sent", "user_id": profile_id}

    def notify_company_whatsapp_linked(self, profile_id: int) -> dict:
        """Notifica empresa via WhatsApp após confirmar vínculo pelo magic link."""
        from apps.users.models import UserProfile

        profile = UserProfile.objects.select_related("company").get(pk=profile_id)
        if not profile.is_company_authenticated or profile.company is None:
            return {"status": "skipped", "reason": "not_authenticated"}

        self._reset_state(profile)

        company_name = profile.company.nome
        client = self._get_client()
        client.send_message(
            profile.phone_number,
            f"✅ *Vínculo confirmado!*\n\n"
            f"Sua conta *{company_name}* está conectada ao IterBot.\n\n"
            f"Digite *menu* para acessar o painel da empresa.",
        )
        logger.info("company_whatsapp_linked_notified", profile_id=profile_id)
        return {"status": "sent", "user_id": profile_id}

    def notify_company_approved(self, company_id: int, portal_base_url: str = "") -> dict:
        """Notifica empresa via WhatsApp quando o admin aprova o cadastro.

        Notifica todos os números WhatsApp vinculados e autenticados à empresa.
        Se nenhum número estiver vinculado, retorna status 'skipped'.
        """
        from apps.core.portal_links import build_portal_url
        from apps.jobs.models.company import Company
        from apps.users.models import UserProfile

        try:
            company = Company.objects.get(pk=company_id)
        except Company.DoesNotExist:
            return {"status": "skipped", "reason": "company_not_found"}

        profiles = UserProfile.objects.filter(
            company=company, is_company_authenticated=True
        ).exclude(phone_number="")

        if not profiles.exists():
            logger.info("company_approved_no_whatsapp", company_id=company_id)
            return {"status": "skipped", "reason": "no_whatsapp_linked"}

        portal_url = build_portal_url(portal_base_url, "/empresas/perfil/") or ""
        portal_line = (
            f"\n📝 *Acesse o portal para gerenciar vagas:*\n{portal_url}\n" if portal_url else ""
        )

        client = self._get_client()
        sent = 0
        for profile in profiles:
            try:
                client.send_message(
                    profile.phone_number,
                    f"✅ *Empresa aprovada!*\n\n"
                    f"Olá, *{company.nome}*! Sua empresa foi aprovada no IterBot UTFPR.\n\n"
                    f"Agora você pode cadastrar vagas para os alunos da UTFPR.{portal_line}\n"
                    f"📱 Digite *menu* aqui no WhatsApp para acessar o painel da empresa e receber notificações.",
                )
                sent += 1
                logger.info(
                    "company_approved_notified",
                    company_id=company_id,
                    phone=profile.phone_number,
                )
            except Exception as exc:
                logger.error(
                    "company_approved_notify_failed",
                    company_id=company_id,
                    phone=profile.phone_number,
                    error=str(exc),
                )

        return {
            "status": "sent" if sent > 0 else "error",
            "company_id": company_id,
            "notified": sent,
        }
