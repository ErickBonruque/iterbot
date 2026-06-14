from unittest.mock import MagicMock, patch

from django.test import TestCase


class TestSendWeeklyReviewsService(TestCase):
    @patch("apps.jobs.services.search_with_config")
    @patch("apps.jobs.services.time.sleep")
    @patch("apps.jobs.services.UserProfile.objects.filter")
    @patch("apps.jobs.services.build_weekly_local_review")
    def test_service_returns_stats_and_uses_interval(
        self, mock_build_review, mock_filter, mock_sleep, mock_search
    ):
        from apps.jobs.services import send_weekly_reviews

        course = MagicMock()
        course.name = "Engenharia"

        user = MagicMock()
        user.id = 1
        user.phone_number = "5511999999999@c.us"
        user.conversation_state.selected_course = course

        users_qs = MagicMock()
        users_qs.count.return_value = 1
        users_qs.__iter__.return_value = iter([user])

        mock_filter.return_value.exclude.return_value.select_related.return_value = users_qs
        mock_build_review.return_value = [{"title": "Dev Python", "company": "TechCorp"}]

        sender = MagicMock()

        stats = send_weekly_reviews(
            message_sender=sender,
            interval_seconds=2,
        )

        self.assertEqual(stats, {"sent": 1, "empty_notice": 0, "errors": 0})
        sender.send_message.assert_called_once()
        mock_sleep.assert_called_once_with(2)
        # Caminho semanal é local-only: jobspy/online não pode ser chamado.
        mock_search.assert_not_called()

    @patch("apps.jobs.services.search_with_config")
    @patch("apps.jobs.services.UserProfile.objects.filter")
    @patch("apps.jobs.services.build_weekly_local_review", return_value=[])
    def test_service_sends_empty_notice_when_no_local_jobs(
        self, _mock_review, mock_filter, mock_search
    ):
        from apps.jobs.services import send_weekly_reviews

        course = MagicMock()
        course.name = "Engenharia"

        user = MagicMock()
        user.id = 1
        user.phone_number = "5511999999999@c.us"
        user.conversation_state.selected_course = course

        users_qs = MagicMock()
        users_qs.count.return_value = 1
        users_qs.__iter__.return_value = iter([user])

        mock_filter.return_value.exclude.return_value.select_related.return_value = users_qs

        sender = MagicMock()

        stats = send_weekly_reviews(
            message_sender=sender,
            interval_seconds=0,
        )

        # Vazio agora ENVIA aviso amigável (não fica em silêncio).
        self.assertEqual(stats, {"sent": 0, "empty_notice": 1, "errors": 0})
        sender.send_message.assert_called_once()
        mock_search.assert_not_called()


class TestWeeklyTaskWrapper(TestCase):
    @patch("apps.jobs.tasks.send_weekly_reviews")
    @patch("infra.waha.client.WahaClient")
    @patch("apps.bot.models.BotConfiguration.get_active")
    def test_task_is_thin_wrapper(
        self,
        mock_get_active,
        mock_waha_client,
        mock_send_weekly_reviews,
    ):
        from apps.jobs.tasks import send_weekly_job_review

        mock_get_active.return_value = MagicMock()
        mock_send_weekly_reviews.return_value = {"sent": 2, "empty_notice": 1, "errors": 0}

        result = send_weekly_job_review()

        self.assertEqual(result, {"sent": 2, "empty_notice": 1, "errors": 0})
        mock_send_weekly_reviews.assert_called_once_with(
            message_sender=mock_waha_client.return_value,
            interval_seconds=1,
        )
