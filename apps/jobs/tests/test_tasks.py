from unittest.mock import MagicMock, patch

from django.test import TestCase

from apps.jobs.tasks import _build_review_for_user, _deduplicate, _format_review_message


class TestFormatReviewMessage(TestCase):
    def test_format_message_header(self):
        jobs = [{"title": "Dev Python", "company": "TechCorp", "job_url": "http://example.com"}]

        message = _format_review_message("Engenharia de Software", jobs)

        self.assertIn("🎓 *Review de Vagas — Engenharia de Software*", message)

    def test_format_message_job_line(self):
        jobs = [{"title": "Dev Python", "company": "TechCorp", "job_url": "http://example.com"}]

        message = _format_review_message("Engenharia", jobs)

        self.assertIn("*1. Dev Python* — TechCorp", message)

    def test_format_message_footer(self):
        jobs = [{"title": "Dev Python", "company": "TechCorp"}]

        message = _format_review_message("Engenharia", jobs)

        self.assertIn("_Para ver mais vagas", message)

    def test_format_message_no_url(self):
        jobs = [{"title": "Dev Python", "company": "TechCorp", "location": "Curitiba"}]

        message = _format_review_message("Engenharia", jobs)

        self.assertNotIn("🔗", message)

    def test_format_message_with_url(self):
        jobs = [{"title": "Dev Python", "company": "TechCorp", "job_url": "http://example.com"}]

        message = _format_review_message("Engenharia", jobs)

        self.assertIn("🔗 http://example.com", message)


class TestDeduplicate(TestCase):
    def test_dedup_removes_same_title_company(self):
        jobs = [
            {"title": "Dev Python", "company": "TechCorp"},
            {"title": "Dev Python", "company": "TechCorp"},
        ]

        unique = _deduplicate(jobs)

        self.assertEqual(len(unique), 1)

    def test_dedup_case_insensitive(self):
        jobs = [
            {"title": "Dev Python", "company": "TechCorp"},
            {"title": "dev python", "company": "techcorp"},
        ]

        unique = _deduplicate(jobs)

        self.assertEqual(len(unique), 1)

    def test_dedup_keeps_different_titles(self):
        jobs = [
            {"title": "Dev Python", "company": "TechCorp"},
            {"title": "Dev Django", "company": "TechCorp"},
        ]

        unique = _deduplicate(jobs)

        self.assertEqual(len(unique), 2)


class TestBuildReviewForUser(TestCase):
    @patch("apps.jobs.tasks._get_online_jobs_for_course")
    @patch("apps.jobs.tasks._get_local_jobs_for_course")
    def test_max_5_vagas(self, local_mock, online_mock):
        local_mock.return_value = [
            {"title": f"Local {i}", "company": "Empresa L"}
            for i in range(4)
        ]
        online_mock.return_value = [
            {"title": f"Online {i}", "company": "Empresa O"}
            for i in range(4)
        ]

        course = MagicMock()
        service = MagicMock()

        jobs = _build_review_for_user(course, service)

        self.assertEqual(len(jobs), 5)
