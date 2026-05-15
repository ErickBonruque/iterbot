from datetime import timedelta

import redis
from django.db.models import Avg, Count, F, Max, Q, Sum
from django.db.models.functions import TruncHour
from django.utils import timezone

from apps.bot.health import BotHealthMonitor
from apps.bot.models import BotConfiguration, BotHealthCheck, BotMetrics, InteractionLog
from config.env import settings
from apps.courses.models import Course
from apps.jobs.models import JobSearchLog
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

    @staticmethod
    def get_search_metrics_context(days: int = 30) -> dict:
        """
        Métricas de busca (METR-01).
        Retorna total de buscas, vagas encontradas, taxa de sucesso,
        vagas por termo (gráfico de barras), e termos mais usados (tabela).
        """
        since = timezone.now() - timedelta(days=days)
        logs_qs = JobSearchLog.objects.filter(created_at__gte=since)

        total_searches = logs_qs.count()
        total_jobs_found = logs_qs.aggregate(total=Sum("results_count"))["total"] or 0
        successful_searches = logs_qs.filter(results_count__gt=0).count()
        search_success_rate = successful_searches / total_searches if total_searches > 0 else 0.0

        # Vagas encontradas por termo (para gráfico de barras — D-10)
        jobs_per_term = list(
            logs_qs.values("search_term")
            .annotate(
                total_results=Sum("results_count"),
                total_searches=Count("id"),
            )
            .order_by("-total_results")
        )

        # Termos mais usados (tabela com detalhes — D-11)
        top_terms = list(
            logs_qs.values("search_term")
            .annotate(
                total_searches=Count("id"),
                total_results=Sum("results_count"),
                last_search=Max("created_at"),
            )
            .order_by("-total_searches")
        )
        # Enriquecer com nome do curso via SearchTerm
        from apps.courses.models import SearchTerm

        term_to_course = {
            st.term: st.course.name
            for st in SearchTerm.objects.select_related("course").all()
        }
        for term_data in top_terms:
            term_data["course_name"] = term_to_course.get(term_data["search_term"], "—")

        return {
            "total_searches": total_searches,
            "total_jobs_found": total_jobs_found,
            "search_success_rate": search_success_rate,
            "jobs_per_term": jobs_per_term,
            "top_terms": top_terms,
        }

    @staticmethod
    def get_user_metrics_context(days: int = 30) -> dict:
        """
        Métricas de usuários (METR-02, D-02).
        Distribuição por curso, engajamento, ativos vs inativos.
        """
        since = timezone.now() - timedelta(days=days)

        total_users = UserProfile.objects.count()

        # Distribuição por curso (D-12) — inclui "Sem curso definido"
        from django.db.models import Case, Value, CharField, When

        course_dist = (
            UserProfile.objects.values(
                course_name=Case(
                    When(course__isnull=False, then=F("course__name")),
                    default=Value("Sem curso definido"),
                    output_field=CharField(),
                )
            )
            .annotate(count=Count("id"))
            .order_by("-count")
        )
        user_distribution = list(course_dist)

        users_with_course = UserProfile.objects.filter(course__isnull=False).count()

        # Engajamento (D-13): interações no período / total de usuários
        period_interactions = InteractionLog.objects.filter(created_at__gte=since).count()
        avg_engagement = period_interactions / total_users if total_users > 0 else 0.0

        # Ativos vs Inativos (D-14)
        active_users = UserProfile.objects.filter(last_activity__gte=since).count()
        inactive_users = total_users - active_users

        return {
            "user_distribution": user_distribution,
            "total_users": total_users,
            "users_with_course": users_with_course,
            "avg_engagement": round(avg_engagement, 2),
            "active_users_count": active_users,
            "inactive_users_count": inactive_users,
        }

    @staticmethod
    def get_auth_funnel_context(days: int = 30) -> dict:
        """
        Funil de autenticação (METR-03, D-15, D-16).
        Cadastros -> Confirmações de email -> Usuários ativos autenticados.
        """
        since = timezone.now() - timedelta(days=days)

        # Etapa 1: Cadastros iniciados (todos os UserProfile)
        signups_count = UserProfile.objects.count()
        # Etapa 2: Confirmações de email concluídas
        email_verified_count = UserProfile.objects.filter(email_verified=True).count()
        # Etapa 3: Usuários autenticados ativos no período
        active_authenticated = UserProfile.objects.filter(
            is_authenticated_utfpr=True,
            last_activity__gte=since,
        ).count()

        # Taxas de conversão (D-16)
        signup_to_email_rate = (
            email_verified_count / signups_count if signups_count > 0 else 0.0
        )
        email_to_active_rate = (
            active_authenticated / email_verified_count if email_verified_count > 0 else 0.0
        )
        overall_conversion_rate = (
            active_authenticated / signups_count if signups_count > 0 else 0.0
        )

        return {
            "signups_count": signups_count,
            "email_verified_count": email_verified_count,
            "active_authenticated_users": active_authenticated,
            "signup_to_email_rate": round(signup_to_email_rate, 3),
            "email_to_active_rate": round(email_to_active_rate, 3),
            "overall_conversion_rate": round(overall_conversion_rate, 3),
        }

    @staticmethod
    def get_business_metrics_context(days: int = 30) -> dict:
        """
        Métricas de negócio completas (METR-01, METR-02, METR-03).
        Orchestrator que une search, user, e auth funnel metrics.
        Período padrão: 30 dias (D-07).
        """
        since = timezone.now() - timedelta(days=days)
        has_search_data = JobSearchLog.objects.filter(created_at__gte=since).exists()

        context = {
            "has_search_data": has_search_data,
            "days": days,
        }

        # Só calcula métricas detalhadas se houver dados (D-20)
        if has_search_data:
            context.update(DashboardService.get_search_metrics_context(days=days))
        else:
            # Retorna estrutura vazia para evitar erros no template
            context.update({
                "total_searches": 0,
                "total_jobs_found": 0,
                "search_success_rate": 0.0,
                "jobs_per_term": [],
                "top_terms": [],
            })

        # User metrics e auth funnel são independentes de JobSearchLog
        context.update(DashboardService.get_user_metrics_context(days=days))
        context.update(DashboardService.get_auth_funnel_context(days=days))

        return context

    @staticmethod
    def get_api_latency_context(hours: int = 24) -> dict:
        since = timezone.now() - timedelta(hours=hours)

        latency_qs = BotMetrics.objects.filter(
            metric_name="api.latency_ms", created_at__gte=since
        )
        total_samples = latency_qs.count()
        has_latency_data = total_samples > 0
        avg_api_latency_ms = latency_qs.aggregate(avg=Avg("value"))["avg"] or 0.0

        latency_timeseries = list(
            latency_qs
            .annotate(hour=TruncHour("created_at"))
            .values("hour")
            .annotate(
                avg_latency_ms=Avg("value"),
                sample_count=Count("id"),
            )
            .order_by("hour")
        )

        bot_logs = InteractionLog.objects.filter(
            created_at__gte=since,
            metadata__has_key="processing_time_ms",
        )
        bot_processing_avg = bot_logs.aggregate(
            avg=Avg("metadata__processing_time_ms")
        )["avg"] or 0.0

        waha_latency = BotHealthCheck.objects.filter(
            created_at__gte=since,
            response_time__isnull=False,
        ).aggregate(avg=Avg("response_time"))["avg"] or 0.0

        return {
            "has_latency_data": has_latency_data,
            "total_api_samples": total_samples,
            "avg_api_latency_ms": round(avg_api_latency_ms, 2),
            "bot_processing_time_ms": round(bot_processing_avg, 2),
            "waha_latency_ms": round(waha_latency, 2),
            "latency_timeseries": [
                {
                    "hour": entry["hour"].isoformat() if entry["hour"] else "",
                    "avg_latency_ms": round(entry["avg_latency_ms"], 2),
                    "sample_count": entry["sample_count"],
                }
                for entry in latency_timeseries
            ],
        }

    @staticmethod
    def get_celery_context() -> dict:
        from django.core.cache import cache

        cached = cache.get("celery_health_context")
        if cached:
            return cached

        from waha_bot.celery import app as celery_app

        inspect = celery_app.control.inspect(timeout=1.0)

        try:
            active = inspect.active() or {}
            reserved = inspect.reserved() or {}
            stats = inspect.stats() or {}
            celery_available = bool(stats)
        except Exception:
            return {"celery_available": False}

        workers = {}
        total_active_tasks = 0
        total_reserved = 0
        total_processed = 0

        for worker_name in stats:
            worker_stats = stats[worker_name]
            worker_active = len(active.get(worker_name, []))
            worker_reserved = len(reserved.get(worker_name, []))
            worker_processed = (
                worker_stats.get("total", {})
                .get("tasks", {})
                .get("all", 0)
            )
            workers[worker_name] = {
                "status": "online",
                "active_tasks": worker_active,
                "reserved_tasks": worker_reserved,
                "total_processed": worker_processed,
            }
            total_active_tasks += worker_active
            total_reserved += worker_reserved
            total_processed += worker_processed

        try:
            r = redis.from_url(settings.redis.url)
            queue_depth = r.llen("celery")
        except Exception:
            queue_depth = -1

        since_24h = timezone.now() - timedelta(hours=24)
        task_failure_count = BotMetrics.objects.filter(
            metric_name="celery.task_failure",
            created_at__gte=since_24h,
        ).count()

        result = {
            "celery_available": True,
            "workers": workers,
            "total_workers": len(workers),
            "total_active_tasks": total_active_tasks,
            "queue_depth": queue_depth,
            "total_reserved": total_reserved,
            "total_processed": total_processed,
            "task_failure_count": task_failure_count,
        }

        cache.set("celery_health_context", result, timeout=30)
        return result

    @staticmethod
    def get_waha_uptime_context(hours: int = 24) -> dict:
        since = timezone.now() - timedelta(hours=hours)
        checks = BotHealthCheck.objects.filter(created_at__gte=since)

        total_checks = checks.count()
        has_waha_data = total_checks > 0

        if not has_waha_data:
            return {
                "has_waha_data": False,
                "waha_history": [],
                "waha_current_status": {"status": "unknown", "session_status": "unknown", "latency_ms": None},
                "waha_degradation": {"has_degradation": False, "degraded_hours": 0, "total_hours": 0, "degradation_pct": 0},
                "period_hours": hours,
            }

        from django.db import models

        hourly = (
            checks
            .annotate(hour=TruncHour("created_at"))
            .values("hour")
            .annotate(
                total=Count("id"),
                online=Count("id", filter=models.Q(status="online")),
                avg_latency=Avg("response_time"),
            )
            .order_by("hour")
        )

        history = []
        degraded_count = 0
        for entry in hourly:
            uptime_pct = (entry["online"] / entry["total"]) * 100 if entry["total"] > 0 else 0
            is_degraded = uptime_pct < 90
            if is_degraded:
                degraded_count += 1
            history.append({
                "time": entry["hour"].isoformat() if entry["hour"] else "",
                "uptime_pct": round(uptime_pct, 1),
                "avg_latency_ms": round(entry["avg_latency"], 1) if entry["avg_latency"] else 0,
                "total_checks": entry["total"],
                "is_degraded": is_degraded,
            })

        latest_check = checks.order_by("-created_at").first()
        online_count = checks.filter(status="online").count()
        overall_uptime_pct = (online_count / total_checks) * 100 if total_checks > 0 else 0

        return {
            "has_waha_data": True,
            "waha_history": history,
            "overall_uptime_pct": round(overall_uptime_pct, 1),
            "waha_current_status": {
                "status": latest_check.status if latest_check else "unknown",
                "session_status": latest_check.session_status if latest_check else "unknown",
                "latency_ms": round(latest_check.response_time, 1) if latest_check and latest_check.response_time else None,
            },
            "waha_degradation": {
                "has_degradation": degraded_count > 0,
                "degraded_hours": degraded_count,
                "total_hours": len(history),
                "degradation_pct": round((degraded_count / len(history)) * 100, 1) if history else 0,
            },
            "period_hours": hours,
        }

    @staticmethod
    def get_technical_metrics_context(hours: int = 24) -> dict:
        context = {
            "period_hours": hours,
        }
        context.update(DashboardService.get_api_latency_context(hours=hours))
        context.update(DashboardService.get_celery_context())
        context.update(DashboardService.get_waha_uptime_context(hours=hours))
        return context
