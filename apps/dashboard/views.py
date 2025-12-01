from datetime import timedelta

from django.db.models import Q
from django.shortcuts import get_object_or_404, render
from django.utils import timezone

from apps.bot.health import BotHealthMonitor
from apps.bot.models import BotConfiguration, BotHealthCheck, InteractionLog
from apps.courses.models import Course
from apps.users.models import UserProfile


def dashboard_home(request):
    """
    Página inicial do dashboard - Overview geral.
    """
    # Estatísticas gerais
    total_courses = Course.objects.filter(is_active=True).count()
    total_interactions = InteractionLog.objects.count()
    total_users = InteractionLog.objects.values("user_id").distinct().count()

    # Últimas interações
    recent_logs = (
        InteractionLog.objects.select_related("user")
        .only("user__phone_number", "message_content", "message_type", "created_at")
        .order_by("-created_at")[:10]
    )

    # Status do bot
    monitor = BotHealthMonitor()
    bot_metrics = monitor.get_metrics_summary(hours=24)

    context = {
        "total_courses": total_courses,
        "total_interactions": total_interactions,
        "total_users": total_users,
        "recent_logs": recent_logs,
        "bot_metrics": bot_metrics,
    }

    return render(request, "dashboard/home_modern.html", context)


def bot_status(request):
    """
    Página de monitoramento detalhado do bot.
    """
    monitor = BotHealthMonitor()

    # Status atual
    current_status = monitor.check_bot_status()

    # Métricas de diferentes períodos
    metrics_1h = monitor.get_metrics_summary(hours=1)
    metrics_24h = monitor.get_metrics_summary(hours=24)
    metrics_7d = monitor.get_metrics_summary(hours=24 * 7)

    # Últimas verificações
    recent_checks = BotHealthCheck.objects.only(
        "status", "response_time", "session_status", "error_message", "created_at"
    ).order_by("-created_at")[:20]

    context = {
        "current_status": current_status,
        "metrics_1h": metrics_1h,
        "metrics_24h": metrics_24h,
        "metrics_7d": metrics_7d,
        "recent_checks": recent_checks,
    }

    return render(request, "dashboard/bot_status.html", context)


def bot_configuration(request):
    """Página para gerenciar credenciais WAHA e login do dashboard."""

    active_config = (
        BotConfiguration.objects.order_by("-created_at").first() or BotConfiguration.defaults()
    )

    context = {
        "active_config": active_config,
    }

    return render(request, "dashboard/bot_configuration.html", context)


def courses_list(request):
    """
    Lista e gerenciamento de cursos.
    """
    courses = Course.objects.prefetch_related("search_terms").all()

    context = {
        "courses": courses,
    }

    return render(request, "dashboard/courses_modern.html", context)


def course_detail(request, course_id):
    """
    Detalhes e gerenciamento de um curso específico.
    """
    course = get_object_or_404(Course.objects.prefetch_related("search_terms"), id=course_id)
    search_terms = course.search_terms.all()

    context = {
        "course": course,
        "search_terms": search_terms,
    }

    return render(request, "dashboard/course_detail.html", context)


def interactions_log(request):
    """
    Histórico de interações com filtros.
    """
    # Filtros
    days = int(request.GET.get("days", 7))
    message_type = request.GET.get("type", "")
    search = request.GET.get("search", "")

    # Query base
    queryset = InteractionLog.objects.select_related("user").order_by("-created_at")

    # Aplicar filtros
    if days:
        since = timezone.now() - timedelta(days=days)
        queryset = queryset.filter(created_at__gte=since)

    if message_type:
        queryset = queryset.filter(message_type=message_type)

    if search:
        queryset = queryset.filter(
            Q(message_content__icontains=search)
            | Q(user__phone_number__icontains=search)
            | Q(user__ra__icontains=search)
        )

    # Paginação manual (ou use Django Paginator)
    logs = queryset[:100]

    # Estatísticas
    stats = {
        "total": queryset.count(),
        "received": queryset.filter(message_type="RECEIVED").count(),
        "sent": queryset.filter(message_type="SENT").count(),
    }

    context = {
        "logs": logs,
        "stats": stats,
        "days": days,
        "message_type": message_type,
        "search": search,
    }

    return render(request, "dashboard/interactions_modern.html", context)


def users_list(request):
    users_qs = UserProfile.objects.select_related("selected_course").order_by("-last_activity")
    total_users = users_qs.count()
    authenticated_users = users_qs.filter(is_authenticated_utfpr=True).count()
    unauthenticated_users = total_users - authenticated_users

    context = {
        "users": users_qs,
        "total_users": total_users,
        "authenticated_users": authenticated_users,
        "unauthenticated_users": unauthenticated_users,
    }

    return render(request, "dashboard/users_modern.html", context)
