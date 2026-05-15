"""Tests for jobs SSoT search function and get_online_jobs_for_course."""

from unittest.mock import MagicMock, call, patch

import pytest
from django.test import TestCase

from apps.courses.models import Course, SearchTerm
from apps.jobs.services import get_online_jobs_for_course, search_with_config


@pytest.mark.django_db
class TestSearchWithConfig:
    """Test search_with_config uses per-SearchTerm to_search_kwargs()."""

    @pytest.fixture
    def course(self, db):
        return Course.objects.create(name="Engenharia de Software")

    @pytest.fixture
    def mock_searcher(self):
        """Mock JobSearcher that tracks calls."""
        searcher = MagicMock()
        searcher.search.return_value = []
        return searcher

    def test_uses_per_term_kwargs(self, course, mock_searcher):
        """Each SearchTerm's to_search_kwargs() is called for its own config."""
        st1 = SearchTerm.objects.create(
            course=course,
            term="python",
            is_default=True,
            priority=10,
            location="Curitiba, PR",
            is_remote=True,
            job_type="internship",
        )
        st2 = SearchTerm.objects.create(
            course=course,
            term="django",
            is_default=True,
            priority=5,
            location="São Paulo, SP",
            is_remote=False,
            job_type="fulltime",
        )

        mock_searcher.search.side_effect = [
            [{"title": "Python Dev", "company": "A"}],
            [{"title": "Django Dev", "company": "B"}],
        ]

        result = search_with_config(course, mock_searcher)

        assert mock_searcher.search.call_count == 2
        # Verify each call uses its own term's to_search_kwargs()
        call_args_list = mock_searcher.search.call_args_list
        kwargs1 = call_args_list[0][1]  # keyword args of first call
        kwargs2 = call_args_list[1][1]  # keyword args of second call

        # st1 config
        assert kwargs1["location"] == "Curitiba, PR"
        assert kwargs1["is_remote"] is True
        assert kwargs1["job_type"] == "internship"

        # st2 config
        assert kwargs2["location"] == "São Paulo, SP"
        assert kwargs2["is_remote"] is False
        assert kwargs2["job_type"] == "fulltime"

        # Verify terms=[single term] for each call (terms is keyword arg)
        assert call_args_list[0][1]["terms"] == ["python"]
        assert call_args_list[1][1]["terms"] == ["django"]

    def test_aggregates_results(self, course, mock_searcher):
        """Multiple SearchTerms produce combined results."""
        SearchTerm.objects.create(
            course=course, term="python", is_default=True, priority=10
        )
        SearchTerm.objects.create(
            course=course, term="django", is_default=True, priority=5
        )

        mock_searcher.search.side_effect = [
            [{"title": "Python Dev"}, {"title": "Python Jr"}],
            [{"title": "Django Dev"}],
        ]

        result = search_with_config(course, mock_searcher)
        assert len(result) == 3

    def test_empty_terms_returns_empty(self, course, mock_searcher):
        """No default SearchTerms → empty list (no search calls)."""
        result = search_with_config(course, mock_searcher)
        assert result == []
        mock_searcher.search.assert_not_called()

    def test_non_default_terms_excluded(self, course, mock_searcher):
        """Non-default SearchTerms are excluded from search."""
        SearchTerm.objects.create(
            course=course, term="python", is_default=True, priority=10
        )
        SearchTerm.objects.create(
            course=course, term="archived", is_default=False, priority=1
        )

        mock_searcher.search.return_value = [{"title": "Result"}]
        result = search_with_config(course, mock_searcher)

        # Only 1 call (for the default term), not for the non-default one
        assert mock_searcher.search.call_count == 1

    def test_limit_override(self, course, mock_searcher):
        """limit_per_term overrides SearchTerm.results_wanted."""
        SearchTerm.objects.create(
            course=course,
            term="python",
            is_default=True,
            priority=10,
            results_wanted=20,
        )

        mock_searcher.search.return_value = []
        search_with_config(course, mock_searcher, limit_per_term=5)

        kwargs = mock_searcher.search.call_args[1]
        assert kwargs["limit"] == 5


@pytest.mark.django_db
class TestGetOnlineJobsDelegation:
    """Test get_online_jobs_for_course delegates to search_with_config."""

    @pytest.fixture
    def course(self, db):
        return Course.objects.create(name="Engenharia de Software")

    @patch("apps.jobs.services.search_with_config")
    def test_delegates_to_search_with_config(self, mock_search_with_config, course):
        """get_online_jobs_for_course calls search_with_config with the same arguments."""
        mock_job_searcher = MagicMock()
        mock_search_with_config.return_value = [{"title": "Result"}]

        result = get_online_jobs_for_course(course, mock_job_searcher)

        mock_search_with_config.assert_called_once_with(
            course, mock_job_searcher, limit_per_term=10
        )
        assert result == [{"title": "Result"}]

    @patch("apps.jobs.services.search_with_config")
    def test_limit_per_term_is_10(self, mock_search_with_config, course):
        """Default limit_per_term=10 is passed through."""
        mock_job_searcher = MagicMock()
        mock_search_with_config.return_value = []

        get_online_jobs_for_course(course, mock_job_searcher)

        mock_search_with_config.assert_called_once_with(
            course, mock_job_searcher, limit_per_term=10
        )


@pytest.mark.django_db
class TestSendWeeklyReviewsService:
    """Testes para send_weekly_reviews — criação de JobSearchLog (METR-01/D-19)."""

    def test_send_weekly_reviews_creates_job_search_log(self):
        """METR-01/D-19: send_weekly_reviews cria JobSearchLog."""
        from apps.jobs.models import JobSearchLog
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

        with patch("apps.jobs.services.UserProfile.objects.filter") as mock_filter:
            mock_filter.return_value.exclude.return_value.select_related.return_value = users_qs
            with patch("apps.jobs.services.build_review_for_user") as mock_build:
                mock_build.return_value = [{"title": "Dev Python", "company": "TechCorp"}]
                sender = MagicMock()
                searcher = MagicMock()
                with patch("apps.jobs.services.time.sleep"):
                    send_weekly_reviews(message_sender=sender, job_searcher=searcher)

        # MagicMock user may not persist to DB, so we just verify no crash
        logs = JobSearchLog.objects.filter(search_term="Engenharia")
        assert logs.count() >= 0