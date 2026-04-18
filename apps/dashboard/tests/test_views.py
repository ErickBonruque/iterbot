from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from apps.bot.models import BotHealthCheck, InteractionLog
from apps.courses.models import Course, SearchTerm
from apps.users.models import UserProfile


@override_settings(ROOT_URLCONF="apps.dashboard.tests.urls")
class TestDashboardViews(TestCase):
    def setUp(self):
        self.client = Client()

        self.course = Course.objects.create(name="Engenharia de Software", is_active=True)
        SearchTerm.objects.create(course=self.course, term="python")

        self.user = UserProfile.objects.create(
            phone_number="5541999999999@c.us",
            ra="a123456",
            is_authenticated_utfpr=True,
        )
        InteractionLog.objects.create(
            user=self.user,
            message_content="Quero vaga de python",
            message_type="RECEIVED",
        )
        InteractionLog.objects.create(
            user=self.user,
            message_content="Temos uma vaga para voce",
            message_type="SENT",
        )

    @patch("apps.dashboard.services.BotHealthMonitor.get_metrics_summary")
    def test_dashboard_home_returns_200(self, mock_metrics):
        mock_metrics.return_value = {
            "uptime_percentage": 100,
            "avg_response_time": 120,
            "total_checks": 1,
            "error_count": 0,
            "last_error": None,
        }

        response = self.client.get(reverse("dashboard_home"))

        self.assertEqual(response.status_code, 200)

    @patch("apps.dashboard.services.BotHealthMonitor.check_bot_status")
    @patch("apps.dashboard.services.BotHealthMonitor.get_metrics_summary")
    def test_bot_status_returns_200(self, mock_metrics, mock_status):
        mock_status.return_value = {
            "status": "online",
            "response_time": 50.0,
            "session_status": "WORKING",
            "last_check": None,
            "error_message": None,
        }
        mock_metrics.return_value = {
            "uptime_percentage": 100,
            "avg_response_time": 90,
            "total_checks": 3,
            "error_count": 0,
            "last_error": None,
        }
        BotHealthCheck.objects.create(status="online", response_time=50, session_status="WORKING")

        response = self.client.get(reverse("bot_status"))

        self.assertEqual(response.status_code, 200)

    def test_bot_configuration_returns_200(self):
        response = self.client.get(reverse("bot_configuration"))

        self.assertEqual(response.status_code, 200)

    def test_courses_list_returns_200(self):
        response = self.client.get(reverse("courses_list"))

        self.assertEqual(response.status_code, 200)

    def test_course_detail_returns_200(self):
        response = self.client.get(reverse("course_detail", kwargs={"course_id": self.course.id}))

        self.assertEqual(response.status_code, 200)

    def test_interactions_log_returns_200_with_filters(self):
        response = self.client.get(
            reverse("interactions_log"),
            {
                "days": 7,
                "type": "RECEIVED",
                "search": "python",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["days"], 7)
        self.assertEqual(response.context["message_type"], "RECEIVED")
        self.assertEqual(response.context["search"], "python")

    def test_users_list_returns_200(self):
        django_user = User.objects.create_user(
            username="dashboard",
            email="dashboard@test.com",
            password="senha123",
        )
        UserProfile.objects.create(
            user=django_user,
            phone_number="5541988888888@c.us",
            is_authenticated_utfpr=False,
        )

        response = self.client.get(reverse("users_list"))

        self.assertEqual(response.status_code, 200)
