from django.contrib import admin
from django.template.response import TemplateResponse
from django.urls import path
from unfold.sites import UnfoldAdminSite


class IterBotAdminSite(UnfoldAdminSite):
    """Site de administração customizado para IterBot UTFPR."""

    site_header = "IterBot UTFPR"
    site_title = "IterBot Admin"
    index_title = "Painel Administrativo"

    def index(self, request, extra_context=None):
        """Adiciona métricas ao contexto da página inicial do admin."""
        from apps.bot.models import BotHealthCheck, InteractionLog
        from apps.jobs.models import Company, CompanyStatus, Job, JobStatus
        from apps.users.models import UserProfile

        extra_context = extra_context or {}

        extra_context["total_alunos"] = UserProfile.objects.exclude(
            user__company__isnull=False
        ).count()
        extra_context["empresas_ativas"] = Company.objects.filter(
            status=CompanyStatus.APPROVED
        ).count()
        extra_context["empresas_pendentes"] = Company.objects.filter(
            status=CompanyStatus.PENDING
        ).count()
        extra_context["vagas_pendentes"] = Job.objects.filter(status=JobStatus.PENDING).count()
        extra_context["vagas_aprovadas"] = Job.objects.filter(status=JobStatus.APPROVED).count()
        extra_context["vagas_total"] = Job.objects.count()
        extra_context["total_interacoes"] = InteractionLog.objects.count()

        ultimo_health = BotHealthCheck.objects.order_by("-created_at").first()
        if ultimo_health:
            extra_context["bot_status"] = ultimo_health.status
            extra_context["bot_response_time"] = ultimo_health.response_time
            extra_context["bot_last_check"] = ultimo_health.created_at
            extra_context["bot_session_status"] = ultimo_health.session_status
        else:
            extra_context["bot_status"] = "unknown"
            extra_context["bot_response_time"] = None
            extra_context["bot_last_check"] = None
            extra_context["bot_session_status"] = "unknown"

        return super().index(request, extra_context=extra_context)

    def get_urls(self):
        custom_urls = [
            path(
                "status-bot/",
                self.admin_view(self.status_bot_view),
                name="status_bot",
            ),
            path(
                "observabilidade/",
                self.admin_view(self.observabilidade_view),
                name="observabilidade",
            ),
            path(
                "metricas-negocio/",
                self.admin_view(self.metricas_negocio_view),
                name="metricas_negocio",
            ),
            path(
                "metricas-tecnicas/",
                self.admin_view(self.metricas_tecnicas_view),
                name="metricas_tecnicas",
            ),
            path(
                "api/waha-status/",
                self.admin_view(self.waha_status_api_view),
                name="waha_status_api",
            ),
            path(
                "api/waha-restart/",
                self.admin_view(self.waha_restart_api_view),
                name="waha_restart_api",
            ),
        ]
        return custom_urls + super().get_urls()

    def status_bot_view(self, request):
        from apps.core.services import DashboardService

        context = {
            **self.each_context(request),
            **DashboardService.get_bot_status_context(),
            "title": "Status do Bot",
        }
        return TemplateResponse(request, "admin/iterbot/status_bot.html", context)

    def observabilidade_view(self, request):
        from apps.bot.models import BotActionLog
        from apps.core.services import DashboardService

        try:
            hours = int(request.GET.get("hours", 24))
        except (ValueError, TypeError):
            hours = 24
        hours = max(1, min(hours, 720))
        action_type = request.GET.get("action_type", "")

        context = {
            **self.each_context(request),
            **DashboardService.get_observability_context(hours=hours, action_type=action_type),
            "title": "Observabilidade",
            "action_type_choices": BotActionLog.ACTION_CHOICES,
        }
        return TemplateResponse(request, "admin/iterbot/observabilidade.html", context)

    def metricas_negocio_view(self, request):
        from apps.core.services import DashboardService

        try:
            days = int(request.GET.get("days", 30))
        except (ValueError, TypeError):
            days = 30
        days = max(1, min(days, 365))

        context = {
            **self.each_context(request),
            **DashboardService.get_business_metrics_context(days=days),
            "title": "Métricas de Negócio",
            "period_days": days,
        }
        return TemplateResponse(request, "admin/iterbot/metricas_negocio.html", context)

    def metricas_tecnicas_view(self, request):
        from apps.core.services import DashboardService

        try:
            hours = int(request.GET.get("hours", 24))
        except (ValueError, TypeError):
            hours = 24
        hours = max(1, min(hours, 720))

        context = {
            **self.each_context(request),
            **DashboardService.get_technical_metrics_context(hours=hours),
            "title": "Métricas Técnicas",
        }
        return TemplateResponse(request, "admin/iterbot/metricas_tecnicas.html", context)

    def waha_status_api_view(self, request):
        from django.core.cache import cache
        from django.http import JsonResponse

        from apps.bot.health import BotHealthMonitor

        # Usar cache populado pelo Celery (TTL 60s) — evita requisição ao WAHA a cada poll do browser
        cached = cache.get("bot_last_status")
        if cached:
            # Converter datetime para string para serialização JSON
            result = dict(cached)
            last_check = result.get("last_check")
            if last_check is not None and hasattr(last_check, "isoformat"):
                result["last_check"] = last_check.isoformat()
            return JsonResponse(result)

        # Cache vazio: checar diretamente (raramente acontece)
        monitor = BotHealthMonitor()
        result = monitor.check_bot_status()
        result["last_check"] = result["last_check"].isoformat()
        return JsonResponse(result)

    def waha_restart_api_view(self, request):
        from django.http import JsonResponse

        from infra.waha.client import WahaClient

        if request.method != "POST":
            return JsonResponse({"error": "Method not allowed"}, status=405)

        try:
            client = WahaClient()
            success = client.start_session()
        except Exception:
            success = False

        return JsonResponse({"success": success})


# Patch the existing admin.site instance's class in-place so all @admin.register()
# decorators (which run before this module is imported) keep their registrations.
admin.site.__class__ = IterBotAdminSite

# Alias used by urls.py
iterbot_admin = admin.site
