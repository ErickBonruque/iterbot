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
    days = int(request.GET.get("days", 7))
    message_type = request.GET.get("type", "")
    search = request.GET.get("search", "")

    context = DashboardService.get_interactions_context(days, message_type, search)

    return render(request, "dashboard/interactions_modern.html", context)


def users_list(request):
    course_filter = request.GET.get("course", "")
    context = DashboardService.get_users_context(course_filter=course_filter)
    return render(request, "dashboard/users_modern.html", context)
