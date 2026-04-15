from unittest.mock import MagicMock, patch

from django.test import TestCase

from apps.jobs.tasks import (
    _build_review_for_user,
    _deduplicate,
    _format_review_message,
    _get_local_jobs_for_course,
)


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


class TestLocalJobsPortalUrl(TestCase):
    def _mock_course_with_search_terms(self):
        course = MagicMock()
        search_terms = MagicMock()
        query_set = MagicMock()
        ordered = MagicMock()

        course.id = 1
        course.name = "Engenharia"
        course.search_terms = search_terms
        search_terms.filter.return_value = query_set
        query_set.order_by.return_value = ordered
        ordered.values_list.return_value = ["python"]

        return course

    @patch("apps.jobs.tasks.Job.objects.filter")
    def test_local_jobs_normalize_trailing_slash(self, filter_mock):
        course = self._mock_course_with_search_terms()

        company = MagicMock(nome="Empresa X", endereco="Curitiba")
        job = MagicMock(titulo="Dev Python", company=company, tipo="Estagio", pk=42)

        filter_mock.return_value.filter.return_value.select_related.return_value.order_by.return_value.__getitem__.return_value = [
            job
        ]

        with self.settings(PORTAL_BASE_URL="https://52-201-248-14.sslip.io/"):
            jobs = _get_local_jobs_for_course(course)

        self.assertEqual(jobs[0]["job_url"], "https://52-201-248-14.sslip.io/empresas/vagas/42/")
        self.assertNotIn("//empresas", jobs[0]["job_url"])

    @patch("apps.jobs.tasks.logger.error")
    @patch("apps.jobs.tasks.Job.objects.filter")
    def test_local_jobs_invalid_base_omits_link(self, filter_mock, logger_error_mock):
        course = self._mock_course_with_search_terms()

        company = MagicMock(nome="Empresa Y", endereco="Curitiba")
        job = MagicMock(titulo="Backend", company=company, tipo="Estagio", pk=7)

        filter_mock.return_value.filter.return_value.select_related.return_value.order_by.return_value.__getitem__.return_value = [
            job
        ]

        with self.settings(PORTAL_BASE_URL="localhost:8000"):
            jobs = _get_local_jobs_for_course(course)

        self.assertIsNone(jobs[0]["job_url"])
        logger_error_mock.assert_called_once_with(
            "invalid_portal_base_url_for_review",
            portal_base_url="localhost:8000",
            job_id=7,
        )

    @patch("apps.jobs.tasks.Job.objects.filter")
    def test_review_message_with_invalid_base_has_no_localhost(self, filter_mock):
        course = self._mock_course_with_search_terms()

        company = MagicMock(nome="Empresa Z", endereco="Curitiba")
        job = MagicMock(titulo="Fullstack", company=company, tipo="Estagio", pk=11)

        filter_mock.return_value.filter.return_value.select_related.return_value.order_by.return_value.__getitem__.return_value = [
            job
        ]

        with self.settings(PORTAL_BASE_URL="localhost:8000"):
            jobs = _get_local_jobs_for_course(course)

        message = _format_review_message("Engenharia", jobs)

        self.assertNotIn("localhost:8000", message)
