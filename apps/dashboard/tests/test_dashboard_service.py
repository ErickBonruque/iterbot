from django.test import TestCase

from apps.courses.models import Course
from apps.dashboard.services import DashboardService
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
