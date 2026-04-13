from django.contrib import admin
from django.db.models import Count, Q


class CapyVagasAdminSite(admin.AdminSite):
    """Site de administração customizado para CapyVagas UTFPR com métricas na home."""

    site_header = "CapyVagas UTFPR"
    site_title = "CapyVagas Admin"
    index_title = "Painel Administrativo"

    def index(self, request, extra_context=None):
        """Adiciona métricas ao contexto da página inicial do admin."""
        from apps.users.models import UserProfile
        from apps.jobs.models import Company, Job, CompanyStatus, JobStatus
        from apps.bot.models import BotHealthCheck, InteractionLog

        extra_context = extra_context or {}

        # Contadores
        extra_context['total_alunos'] = UserProfile.objects.count()
        extra_context['empresas_ativas'] = Company.objects.filter(
            status=CompanyStatus.APPROVED
        ).count()
        extra_context['empresas_pendentes'] = Company.objects.filter(
            status=CompanyStatus.PENDING
        ).count()
        extra_context['vagas_pendentes'] = Job.objects.filter(
            status=JobStatus.PENDING
        ).count()
        extra_context['vagas_aprovadas'] = Job.objects.filter(
            status=JobStatus.APPROVED
        ).count()
        extra_context['vagas_total'] = Job.objects.count()
        extra_context['total_interacoes'] = InteractionLog.objects.count()

        # Status do bot
        ultimo_health = BotHealthCheck.objects.order_by('-created_at').first()
        if ultimo_health:
            extra_context['bot_status'] = ultimo_health.status
            extra_context['bot_response_time'] = ultimo_health.response_time
            extra_context['bot_last_check'] = ultimo_health.created_at
            extra_context['bot_session_status'] = ultimo_health.session_status
        else:
            extra_context['bot_status'] = 'unknown'
            extra_context['bot_response_time'] = None
            extra_context['bot_last_check'] = None
            extra_context['bot_session_status'] = 'unknown'

        return super().index(request, extra_context=extra_context)


# Patch the existing admin.site instance's class in-place so all @admin.register()
# decorators (which run before this module is imported) keep their registrations.
admin.site.__class__ = CapyVagasAdminSite

# Alias used by urls.py
capyvagas_admin = admin.site
