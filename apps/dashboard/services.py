from datetime import timedelta

from django.db.models import Q
from django.utils import timezone

from apps.bot.health import BotHealthMonitor
from apps.bot.models import BotConfiguration, BotHealthCheck, InteractionLog
from apps.courses.models import Course
from apps.users.models import UserProfile


class DashboardService:
    @staticmethod
    def get_home_context():
        total_courses = Course.objects.filter(is_active=True).count()
        total_interactions = InteractionLog.objects.count()
        total_users = InteractionLog.objects.values("user_id").distinct().count()

        recent_logs = (
            InteractionLog.objects.select_related("user")
            .only("user__phone_number", "message_content", "message_type", "created_at")
            .order_by("-created_at")[:10]
        )

        bot_metrics = BotHealthMonitor().get_metrics_summary(hours=24)

        return {
            "total_courses": total_courses,
            "total_interactions": total_interactions,
            "total_users": total_users,
            "recent_logs": recent_logs,
            "bot_metrics": bot_metrics,
        }

    @staticmethod
    def get_bot_status_context():
        monitor = BotHealthMonitor()

        current_status = monitor.check_bot_status()
        metrics_1h = monitor.get_metrics_summary(hours=1)
        metrics_24h = monitor.get_metrics_summary(hours=24)
        metrics_7d = monitor.get_metrics_summary(hours=24 * 7)

        recent_checks = BotHealthCheck.objects.only(
            "status", "response_time", "session_status", "error_message", "created_at"
        ).order_by("-created_at")[:20]

        return {
            "current_status": current_status,
            "metrics_1h": metrics_1h,
            "metrics_24h": metrics_24h,
            "metrics_7d": metrics_7d,
            "recent_checks": recent_checks,
        }

    @staticmethod
    def get_active_bot_configuration():
        return (
            BotConfiguration.objects.order_by("-created_at").first() or BotConfiguration.defaults()
        )

    @staticmethod
    def list_courses_with_terms():
        return Course.objects.prefetch_related("search_terms").all()

    @staticmethod
    def get_course_with_terms(course_id):
        course = Course.objects.prefetch_related("search_terms").get(id=course_id)
        return {
            "course": course,
            "search_terms": course.search_terms.all(),
        }

    @staticmethod
    def get_interactions_context(days, message_type, search):
        queryset = InteractionLog.objects.select_related("user").order_by("-created_at")

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

        logs = queryset[:100]
        stats = {
            "total": queryset.count(),
            "received": queryset.filter(message_type="RECEIVED").count(),
            "sent": queryset.filter(message_type="SENT").count(),
        }

        return {
            "logs": logs,
            "stats": stats,
            "days": days,
            "message_type": message_type,
            "search": search,
        }

    @staticmethod
    def get_users_context(course_filter: str = ""):
        users_qs = UserProfile.objects.select_related("course").order_by("-last_activity")

        if course_filter == "none":
            users_qs = users_qs.filter(course__isnull=True)
        elif course_filter:
            try:
                course_id = int(course_filter)
                users_qs = users_qs.filter(course_id=course_id)
            except ValueError:
                pass  # ignora filtro inválido — proteção contra query param manipulation (T-46-01)

        total_users = UserProfile.objects.count()
        authenticated_users = UserProfile.objects.filter(is_authenticated_utfpr=True).count()
        users_with_course = UserProfile.objects.filter(course__isnull=False).count()
        active_courses_count = (
            UserProfile.objects.filter(course__isnull=False)
            .values("course_id")
            .distinct()
            .count()
        )
        courses_for_filter = Course.objects.filter(is_active=True).order_by("order", "name")

        return {
            "users": users_qs,
            "total_users": total_users,
            "authenticated_users": authenticated_users,
            "unauthenticated_users": total_users - authenticated_users,
            "users_with_course": users_with_course,
            "active_courses_count": active_courses_count,
            "courses_for_filter": courses_for_filter,
            "selected_course_filter": course_filter,
        }
