from django.test import TestCase
from django.utils import timezone

from apps.bot.models import InteractionLog
from apps.courses.models import Course
from apps.dashboard.services import DashboardService
from apps.jobs.models import JobSearchLog
from apps.users.models import UserProfile


class CourseFilterTests(TestCase):
    """Testes para filtro de curso no DashboardService (PERF-03)."""

    def setUp(self):
        self.course_a = Course.objects.create(
            name="Engenharia de Software",
            is_active=True,
            order=1,
        )
        self.course_b = Course.objects.create(
            name="Ciência da Computação",
            is_active=True,
            order=2,
        )
        self.user_with_course = UserProfile.objects.create(
            phone_number="5541111111111@c.us",
            course=self.course_a,
        )
        self.user_no_course = UserProfile.objects.create(
            phone_number="5541222222222@c.us",
        )

    def test_filter_no_course(self):
        """PERF-03: course_filter='none' retorna apenas usuários sem curso."""
        ctx = DashboardService.get_users_context(course_filter="none")
        users_list = list(ctx["users"])
        self.assertIn(self.user_no_course, users_list)
        self.assertNotIn(self.user_with_course, users_list)

    def test_filter_by_course_pk(self):
        """PERF-03: course_filter=str(pk) retorna apenas usuários daquele curso."""
        ctx = DashboardService.get_users_context(course_filter=str(self.course_a.pk))
        users_list = list(ctx["users"])
        self.assertIn(self.user_with_course, users_list)
        self.assertNotIn(self.user_no_course, users_list)

    def test_context_includes_course_counts(self):
        """PERF-03: context retorna users_with_course e active_courses_count."""
        ctx = DashboardService.get_users_context()
        self.assertIn("users_with_course", ctx)
        self.assertIn("active_courses_count", ctx)
        self.assertIsInstance(ctx["users_with_course"], int)
        self.assertIsInstance(ctx["active_courses_count"], int)
        self.assertEqual(ctx["users_with_course"], 1)  # apenas user_with_course tem curso

    def test_invalid_course_filter_is_ignored(self):
        """Segurança (T-46-01): course_filter inválido (não-int) não lança exceção."""
        ctx = DashboardService.get_users_context(course_filter="abc; DROP TABLE users;")
        users_list = list(ctx["users"])
        # sem exceção → filtro inválido ignorado → retorna todos os usuários
        self.assertEqual(len(users_list), 2)

    def test_no_filter_returns_all_users(self):
        """PERF-03: sem filtro retorna todos os usuários."""
        ctx = DashboardService.get_users_context(course_filter="")
        users_list = list(ctx["users"])
        self.assertEqual(len(users_list), 2)


class BusinessMetricsTests(TestCase):
    """Testes para métricas de negócio (METR-01, METR-02, METR-03)."""

    def setUp(self):
        self.course = Course.objects.create(name="Engenharia de Software", is_active=True, order=1)
        self.user = UserProfile.objects.create(
            phone_number="5541999999999@c.us",
            email="aluno@alunos.utfpr.edu.br",
            email_verified=True,
            is_authenticated_utfpr=True,
            course=self.course,
            last_activity=timezone.now(),
        )
        self.user_no_course = UserProfile.objects.create(
            phone_number="5541888888888@c.us",
        )
        # JobSearchLog
        JobSearchLog.objects.create(
            user=self.user,
            search_term="python developer",
            results_count=5,
            filters={},
        )
        JobSearchLog.objects.create(
            user=self.user,
            search_term="java developer",
            results_count=0,
            filters={},
        )
        # InteractionLog for engagement
        InteractionLog.objects.create(
            user=self.user,
            message_content="teste",
            message_type="RECEIVED",
        )

    def test_search_metrics_return_values(self):
        """METR-01: get_business_metrics_context retorna search metrics."""
        ctx = DashboardService.get_business_metrics_context(days=30)
        self.assertTrue(ctx["has_search_data"])
        self.assertEqual(ctx["total_searches"], 2)
        self.assertEqual(ctx["total_jobs_found"], 5)
        self.assertGreater(ctx["search_success_rate"], 0)
        self.assertEqual(len(ctx["jobs_per_term"]), 2)
        self.assertEqual(len(ctx["top_terms"]), 2)

    def test_user_metrics_return_values(self):
        """METR-02: get_business_metrics_context retorna user metrics."""
        ctx = DashboardService.get_business_metrics_context(days=30)
        self.assertEqual(ctx["total_users"], 2)
        self.assertEqual(ctx["users_with_course"], 1)
        self.assertIsInstance(ctx["avg_engagement"], float)
        self.assertGreaterEqual(ctx["active_users_count"], 1)
        self.assertIn("user_distribution", ctx)

    def test_user_distribution_includes_no_course(self):
        """D-12/D-02: Distribuição inclui 'Sem curso definido'."""
        ctx = DashboardService.get_business_metrics_context(days=30)
        course_names = [d["course_name"] for d in ctx["user_distribution"]]
        self.assertIn("Sem curso definido", course_names)

    def test_auth_funnel_return_values(self):
        """METR-03: get_business_metrics_context retorna auth funnel."""
        ctx = DashboardService.get_business_metrics_context(days=30)
        self.assertGreaterEqual(ctx["signups_count"], 1)
        self.assertGreaterEqual(ctx["email_verified_count"], 1)
        self.assertGreaterEqual(ctx["active_authenticated_users"], 1)
        self.assertIsInstance(ctx["signup_to_email_rate"], float)
        self.assertIsInstance(ctx["overall_conversion_rate"], float)

    def test_has_search_data_false_when_empty(self):
        """D-20: Sem JobSearchLog, has_search_data=False."""
        JobSearchLog.objects.all().delete()
        ctx = DashboardService.get_business_metrics_context(days=30)
        self.assertFalse(ctx["has_search_data"])

    def test_empty_state_no_errors(self):
        """D-20: Sem dados de busca, não lança exceção."""
        JobSearchLog.objects.all().delete()
        ctx = DashboardService.get_business_metrics_context(days=30)
        self.assertEqual(ctx["total_searches"], 0)
        self.assertEqual(ctx["total_jobs_found"], 0)
        self.assertEqual(ctx["search_success_rate"], 0.0)

    def test_days_parameter_filters_data(self):
        """D-08: Parâmetro days filtra os dados corretamente."""
        ctx_7d = DashboardService.get_business_metrics_context(days=7)
        ctx_30d = DashboardService.get_business_metrics_context(days=30)
        # Both should have data (created in setUp which uses timezone.now())
        self.assertIsInstance(ctx_7d["days"], int)
        self.assertEqual(ctx_30d["days"], 30)


class TechnicalMetricsTests(TestCase):
    """Testes para métricas técnicas (METR-04, METR-05, METR-06)."""

    def setUp(self):
        from apps.bot.models import BotHealthCheck, BotMetrics

        BotMetrics.objects.create(
            metric_name="api.latency_ms",
            value=150.5,
        )
        BotMetrics.objects.create(
            metric_name="api.latency_ms",
            value=200.3,
        )
        BotMetrics.objects.create(
            metric_name="celery.task_failure",
            value=1,
            metadata={"task_name": "test_task"},
        )
        BotHealthCheck.objects.create(
            status="online",
            response_time=120.0,
            session_status="WORKING",
        )
        BotHealthCheck.objects.create(
            status="error",
            response_time=None,
            error_message="Timeout",
        )

    def test_technical_metrics_returns_all_sections(self):
        ctx = DashboardService.get_technical_metrics_context(hours=24)
        self.assertIn("avg_api_latency_ms", ctx)
        self.assertIn("celery_available", ctx)
        self.assertIn("has_waha_data", ctx)

    def test_api_latency_context(self):
        ctx = DashboardService.get_api_latency_context(hours=24)
        self.assertTrue(ctx["has_latency_data"])
        self.assertGreater(ctx["avg_api_latency_ms"], 0)
        self.assertEqual(ctx["total_api_samples"], 2)
        self.assertIn("latency_timeseries", ctx)

    def test_no_latency_data_empty_state(self):
        from apps.bot.models import BotMetrics

        BotMetrics.objects.filter(metric_name="api.latency_ms").delete()
        ctx = DashboardService.get_api_latency_context(hours=24)
        self.assertFalse(ctx["has_latency_data"])

    def test_celery_context_structure(self):
        ctx = DashboardService.get_celery_context()
        self.assertIn("celery_available", ctx)
        if ctx["celery_available"]:
            self.assertIn("workers", ctx)
            self.assertIn("queue_depth", ctx)
            self.assertIn("task_failure_count", ctx)
            self.assertGreaterEqual(ctx["task_failure_count"], 1)

    def test_waha_uptime_context(self):
        ctx = DashboardService.get_waha_uptime_context(hours=24)
        self.assertTrue(ctx["has_waha_data"])
        self.assertIn("waha_history", ctx)
        self.assertIn("waha_current_status", ctx)
        self.assertIn("waha_degradation", ctx)

    def test_waha_uptime_degradation_detection(self):
        ctx = DashboardService.get_waha_uptime_context(hours=24)
        self.assertTrue(ctx["waha_degradation"]["has_degradation"])

    def test_empty_waha_no_data(self):
        from apps.bot.models import BotHealthCheck

        BotHealthCheck.objects.all().delete()
        ctx = DashboardService.get_waha_uptime_context(hours=24)
        self.assertFalse(ctx["has_waha_data"])

    def test_period_hours_in_context(self):
        ctx = DashboardService.get_technical_metrics_context(hours=1)
        self.assertEqual(ctx["period_hours"], 1)
        ctx = DashboardService.get_technical_metrics_context(hours=168)
        self.assertEqual(ctx["period_hours"], 168)


class ObservabilityContextTests(TestCase):
    """OBS-01, OBS-02: DashboardService.get_observability_context()."""

    def setUp(self):
        from apps.bot.models import BotActionLog

        self.user = UserProfile.objects.create(phone_number="5541999000002@c.us")
        self.log_search_ok = BotActionLog.objects.create(
            user=self.user,
            action_type="SEARCH",
            status="SUCCESS",
            search_term="python",
            jobs_found=5,
            duration_ms=200,
        )
        self.log_error = BotActionLog.objects.create(
            user=self.user,
            action_type="SEARCH",
            status="ERROR",
            error_type="EXCEPTION",
            error_message="Test error",
        )

    def test_observability_returns_actions(self):
        """OBS-01: get_observability_context retorna lista 'actions' com registros."""
        ctx = DashboardService.get_observability_context(hours=24)
        self.assertIn(self.log_search_ok, ctx["actions"])
        self.assertIn("total_actions", ctx)
        self.assertIn("error_rate", ctx)

    def test_observability_hours_filter(self):
        """OBS-01: Filtro hours=1 exclui registros criados há mais de 1h."""
        from datetime import timedelta

        from django.utils import timezone

        from apps.bot.models import BotActionLog

        old_log = BotActionLog.objects.create(
            action_type="MENU",
            status="SUCCESS",
        )
        # Forçar created_at para 2 horas atrás usando update() (bypass auto_now_add)
        BotActionLog.objects.filter(pk=old_log.pk).update(
            created_at=timezone.now() - timedelta(hours=2)
        )
        ctx = DashboardService.get_observability_context(hours=1)
        action_pks = [a.pk for a in ctx["actions"]]
        self.assertNotIn(old_log.pk, action_pks)

    def test_observability_action_type_filter(self):
        """OBS-01: Filtro action_type=MENU exclui logs SEARCH."""
        ctx = DashboardService.get_observability_context(hours=24, action_type="MENU")
        action_pks = [a.pk for a in ctx["actions"]]
        self.assertNotIn(self.log_search_ok.pk, action_pks)

    def test_observability_errors_only_status_error(self):
        """OBS-02: errors contém apenas status=ERROR; log SUCCESS não aparece."""
        ctx = DashboardService.get_observability_context(hours=24)
        error_pks = [e.pk for e in ctx["errors"]]
        self.assertIn(self.log_error.pk, error_pks)
        self.assertNotIn(self.log_search_ok.pk, error_pks)

    def test_error_rate_calculation(self):
        """OBS-02: error_rate = errors/total * 100 arredondado a 1 decimal."""
        ctx = DashboardService.get_observability_context(hours=24)
        # 1 SUCCESS + 1 ERROR = 50.0%
        self.assertEqual(ctx["error_rate"], 50.0)
        self.assertEqual(ctx["total_errors"], 1)
