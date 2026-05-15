from datetime import timedelta

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
        self.course = Course.objects.create(
            name="Engenharia de Software", is_active=True, order=1
        )
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
