"""Tests for DashboardAuthMiddleware."""

from django.contrib.auth.models import AnonymousUser, User
from django.http import HttpResponse
from django.test import RequestFactory, TestCase

from infra.middleware.dashboard_auth import DashboardAuthMiddleware


class TestDashboardAuthMiddleware(TestCase):
    """DashboardAuthMiddleware redirects non-staff, lets staff through."""

    def setUp(self):
        self.factory = RequestFactory()
        self.middleware = DashboardAuthMiddleware(lambda r: HttpResponse("ok"))
        self.staff_user = User.objects.create_user(
            username="staff",
            email="staff@test.com",
            password="pass",
            is_staff=True,
        )
        self.regular_user = User.objects.create_user(
            username="regular",
            email="regular@test.com",
            password="pass",
            is_staff=False,
        )

    def test_unauthenticated_redirect_to_login(self):
        request = self.factory.get("/dashboard/")
        request.user = AnonymousUser()
        response = self.middleware(request)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response.url)
        self.assertIn("next=%2Fdashboard%2F", response.url)

    def test_non_staff_redirect_to_login(self):
        request = self.factory.get("/dashboard/metrics/")
        request.user = self.regular_user
        response = self.middleware(request)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response.url)

    def test_staff_passes_through(self):
        request = self.factory.get("/dashboard/")
        request.user = self.staff_user
        response = self.middleware(request)
        self.assertEqual(response.status_code, 200)

    def test_non_dashboard_path_passes_for_any_user(self):
        for url in ["/admin/", "/health/", "/webhook/", "/api/status/"]:
            request = self.factory.get(url)
            request.user = AnonymousUser()
            response = self.middleware(request)
            self.assertEqual(
                response.status_code, 200,
                f"Rota {url} deveria passar sem redirecionamento",
            )

    def test_next_url_preserved(self):
        target = "/dashboard/metrics/technical/?hours=24"
        request = self.factory.get(target)
        request.user = AnonymousUser()
        response = self.middleware(request)
        self.assertIn("next=%2Fdashboard%2Fmetrics%2Ftechnical%2F", response.url)
