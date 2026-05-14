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
        )
        self.user_no_course = UserProfile.objects.create(
            phone_number="5541222222222@c.us",
        )

    def test_filter_no_course(self):
        """PERF-03: course_filter='none' retorna apenas usuários sem curso."""
        raise NotImplementedError("Stub — implementar após Wave 3 (dashboard service)")

    def test_filter_by_course_pk(self):
        """PERF-03: course_filter=str(pk) retorna apenas usuários daquele curso."""
        raise NotImplementedError("Stub — implementar após Wave 3 (dashboard service)")

    def test_context_includes_course_counts(self):
        """PERF-03: context retorna users_with_course e active_courses_count."""
        raise NotImplementedError("Stub — implementar após Wave 3 (dashboard service)")

    def test_invalid_course_filter_is_ignored(self):
        """Segurança (T-46-01): course_filter inválido (não-int) não lança exceção."""
        raise NotImplementedError("Stub — implementar após Wave 3 (dashboard service)")

    def test_no_filter_returns_all_users(self):
        """PERF-03: sem filtro retorna todos os usuários."""
        raise NotImplementedError("Stub — implementar após Wave 3 (dashboard service)")
