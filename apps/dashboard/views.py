from django.http import Http404
from django.shortcuts import render

from apps.dashboard.services import DashboardService


def dashboard_home(request):
    """
    Página inicial do dashboard - Overview geral.
    """
    context = DashboardService.get_home_context()

    return render(request, "dashboard/home_modern.html", context)


def bot_status(request):
    """
    Página de monitoramento detalhado do bot.
    """
    context = DashboardService.get_bot_status_context()

    return render(request, "dashboard/bot_status.html", context)


def bot_configuration(request):
    """Página para gerenciar credenciais WAHA e login do dashboard."""

    active_config = DashboardService.get_active_bot_configuration()

    context = {
        "active_config": active_config,
    }

    return render(request, "dashboard/bot_configuration.html", context)


def courses_list(request):
    """
    Lista e gerenciamento de cursos.
    """
    courses = DashboardService.list_courses_with_terms()

    context = {
        "courses": courses,
    }

    return render(request, "dashboard/courses_modern.html", context)


def course_detail(request, course_id):
    """
    Detalhes e gerenciamento de um curso específico.
    """
    try:
        course_data = DashboardService.get_course_with_terms(course_id)
    except Exception as err:
        raise Http404("Curso não encontrado.") from err

    context = {
        "course": course_data["course"],
        "search_terms": course_data["search_terms"],
    }

    return render(request, "dashboard/course_detail.html", context)


def interactions_log(request):
    """
    Histórico de interações com filtros.
    """
    # Filtros
    try:
        days = int(request.GET.get("days", 7))
    except (ValueError, TypeError):
        days = 7
    message_type = request.GET.get("type", "")
    search = request.GET.get("search", "")

    context = DashboardService.get_interactions_context(days, message_type, search)

    return render(request, "dashboard/interactions_modern.html", context)


def users_list(request):
    course_filter = request.GET.get("course", "")
    context = DashboardService.get_users_context(course_filter=course_filter)
    return render(request, "dashboard/users_modern.html", context)


def business_metrics(request):
    """
    Página de métricas de negócio (METR-01, METR-02, METR-03).
    Exibe search metrics, user metrics e auth funnel com período selecionável.
    """
    try:
        days = int(request.GET.get("days", 30))
    except (ValueError, TypeError):
        days = 30
    # Valida range: 1-365 dias (T-47-03-01)
    if days < 1:
        days = 30
    elif days > 365:
        days = 365

    context = DashboardService.get_business_metrics_context(days=days)

    return render(request, "dashboard/business_metrics.html", context)


def observability(request):
    """
    Página de observabilidade do bot (OBS-01, OBS-02, OBS-03).
    Exibe log de ações e erros recentes com filtros de período e tipo.
    Validação: hours entre 1 e 720; action_type passado direto ao service (ORM parameterized).
    """
    try:
        hours = int(request.GET.get("hours", 24))
    except (ValueError, TypeError):
        hours = 24
    if hours < 1:
        hours = 24
    elif hours > 720:
        hours = 720

    action_type = request.GET.get("action_type", "")

    context = DashboardService.get_observability_context(hours=hours, action_type=action_type)
    return render(request, "dashboard/observability.html", context)


def technical_metrics(request):
    """
    Página de métricas técnicas (METR-04, METR-05, METR-06).
    Exibe API latency, Celery health e WAHA uptime com período selecionável.
    """
    try:
        hours = int(request.GET.get("hours", 24))
    except (ValueError, TypeError):
        hours = 24
    if hours < 1:
        hours = 24
    elif hours > 720:
        hours = 720

    context = DashboardService.get_technical_metrics_context(hours=hours)

    return render(request, "dashboard/technical_metrics.html", context)
