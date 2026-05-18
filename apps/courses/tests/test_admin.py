from unittest.mock import patch

import pytest
from django.test import Client

from apps.courses.admin import ACTION_KEY
from apps.courses.models import Course, SearchTerm


@pytest.fixture
def course(db):
    return Course.objects.create(name="Engenharia de Software")


@pytest.fixture
def search_term(course):
    return SearchTerm.objects.create(course=course, term="python")


@pytest.fixture
def admin_user(db):
    from django.contrib.auth import get_user_model

    user_model = get_user_model()
    return user_model.objects.create_superuser(
        username="admin", password="pass", email="admin@test.com"
    )


@pytest.fixture
def client():
    return Client()


@pytest.mark.django_db
class TestSearchTermAdminFieldsets:
    def test_change_view_contains_fieldsets(self, client, admin_user, search_term):
        client.force_login(admin_user)
        url = f"/admin/courses/searchterm/{search_term.pk}/change/"
        response = client.get(url)
        assert response.status_code == 200
        content = response.content.decode()
        assert "Identificação" in content
        assert "Sites de Busca" in content
        assert "Filtros de Busca" in content


@pytest.mark.django_db
class TestTestSearchAction:
    @patch("infra.jobspy.service.JobSearchService.search")
    def test_action_redirects_with_results(self, mock_search, client, admin_user, search_term):
        mock_search.return_value = [
            {
                "title": "Python Developer",
                "company": "Test Corp",
                "location": "Curitiba, PR",
                "job_url": "https://example.com/job/1",
            }
        ]
        client.force_login(admin_user)
        url = f"/admin/courses/searchterm/{search_term.pk}/change/"
        data = {
            ACTION_KEY: "1",
            "_save": "1",
            "course": search_term.course_id,
            "term": search_term.term,
            "is_default": "1",
            "priority": "0",
            "site_name": "linkedin,indeed,glassdoor",
            "location": "Curitiba, PR",
            "results_wanted": "10",
            "hours_old": "72",
            "country_indeed": "Brazil",
            "offset": "0",
            "is_remote": "0",
            "linkedin_fetch_description": "0",
        }
        response = client.post(url, data=data, follow=True)
        assert response.status_code == 200
        content = response.content.decode()
        assert "Python Developer" in content or "job_results" in str(response.context)

    @patch("infra.jobspy.service.JobSearchService.search")
    def test_action_empty_results_with_warning(self, mock_search, client, admin_user, search_term):
        mock_search.return_value = []
        client.force_login(admin_user)
        url = f"/admin/courses/searchterm/{search_term.pk}/change/"
        data = {
            ACTION_KEY: "1",
            "_save": "1",
            "course": search_term.course_id,
            "term": search_term.term,
            "is_default": "1",
            "priority": "0",
            "site_name": "linkedin,indeed,glassdoor",
            "location": "Curitiba, PR",
            "results_wanted": "10",
            "hours_old": "72",
            "country_indeed": "Brazil",
            "offset": "0",
            "is_remote": "0",
            "linkedin_fetch_description": "0",
        }
        response = client.post(url, data=data, follow=True)
        assert response.status_code == 200

    @patch("infra.jobspy.service.JobSearchService.search")
    def test_action_exception_handled(self, mock_search, client, admin_user, search_term):
        mock_search.side_effect = Exception("API error")
        client.force_login(admin_user)
        url = f"/admin/courses/searchterm/{search_term.pk}/change/"
        data = {
            ACTION_KEY: "1",
            "_save": "1",
            "course": search_term.course_id,
            "term": search_term.term,
            "is_default": "1",
            "priority": "0",
            "site_name": "linkedin,indeed,glassdoor",
            "location": "Curitiba, PR",
            "results_wanted": "10",
            "hours_old": "72",
            "country_indeed": "Brazil",
            "offset": "0",
            "is_remote": "0",
            "linkedin_fetch_description": "0",
        }
        response = client.post(url, data=data, follow=True)
        assert response.status_code == 200

    @patch("infra.jobspy.service.JobSearchService.search")
    def test_test_search_creates_job_search_log(self, mock_search, client, admin_user, search_term):
        """METR-01/D-18: test_search cria JobSearchLog com results."""
        from apps.jobs.models import JobSearchLog

        mock_search.return_value = [
            {"title": "Python Developer", "company": "Test Corp"},
        ]
        client.force_login(admin_user)
        url = f"/admin/courses/searchterm/{search_term.pk}/change/"
        data = {
            ACTION_KEY: "1",
            "_save": "1",
            "course": search_term.course_id,
            "term": search_term.term,
            "is_default": "1",
            "priority": "0",
            "site_name": "linkedin,indeed,glassdoor",
            "location": "Curitiba, PR",
            "results_wanted": "10",
            "hours_old": "72",
            "country_indeed": "Brazil",
            "offset": "0",
            "is_remote": "0",
            "linkedin_fetch_description": "0",
        }
        client.post(url, data=data, follow=True)
        logs = JobSearchLog.objects.filter(search_term="python")
        assert logs.count() >= 1
        log = logs.first()
        assert log is not None
        assert log.user is None  # D-18: admin searches have user=None
        assert log.results_count == 1


@pytest.mark.django_db
class TestNoStaleSearchMessage:
    """Verify FIX-02: no stale messages.info 'Executando busca' after results load.

    We test the admin method directly (unit-level) to reliably detect whether
    messages.info() is called — the HTTP integration test with follow=True
    loses messages through the redirect cycle.
    """

    @patch("infra.jobspy.service.JobSearchService.search")
    def test_no_stale_info_message_on_success(self, mock_search, rf, admin_user, search_term):
        """After successful search, test_search must NOT add messages.info with 'Executando busca'."""
        from django.contrib.messages import constants as message_constants
        from django.contrib.messages.storage.fallback import FallbackStorage

        from apps.courses.admin import SearchTermAdmin

        mock_search.return_value = [
            {"title": "Python Dev", "company": "Corp", "location": "Curitiba, PR"}
        ]
        request = rf.post(f"/admin/courses/searchterm/{search_term.pk}/change/")
        request.user = admin_user
        # Set up messages middleware on the request
        request.session = {}
        request._messages = FallbackStorage(request)

        admin_instance = SearchTermAdmin(SearchTerm, None)
        admin_instance.test_search(request, search_term)

        messages_list = list(request._messages)
        info_messages = [m for m in messages_list if m.level == message_constants.INFO]
        assert not any("Executando busca" in str(m.message) for m in info_messages), (
            f"Found stale 'Executando busca' info message: {[m.message for m in info_messages]}"
        )

    @patch("infra.jobspy.service.JobSearchService.search")
    def test_no_stale_info_message_on_empty(self, mock_search, rf, admin_user, search_term):
        """After empty results, test_search must NOT add messages.info with 'Executando busca'."""
        from django.contrib.messages import constants as message_constants
        from django.contrib.messages.storage.fallback import FallbackStorage

        from apps.courses.admin import SearchTermAdmin

        mock_search.return_value = []
        request = rf.post(f"/admin/courses/searchterm/{search_term.pk}/change/")
        request.user = admin_user
        request.session = {}
        request._messages = FallbackStorage(request)

        admin_instance = SearchTermAdmin(SearchTerm, None)
        admin_instance.test_search(request, search_term)

        messages_list = list(request._messages)
        info_messages = [m for m in messages_list if m.level == message_constants.INFO]
        assert not any("Executando busca" in str(m.message) for m in info_messages), (
            f"Found stale 'Executando busca' info message: {[m.message for m in info_messages]}"
        )

    @patch("infra.jobspy.service.JobSearchService.search")
    def test_no_stale_info_message_on_error(self, mock_search, rf, admin_user, search_term):
        """After an exception, test_search must NOT add messages.info with 'Executando busca'."""
        from django.contrib.messages import constants as message_constants
        from django.contrib.messages.storage.fallback import FallbackStorage

        from apps.courses.admin import SearchTermAdmin

        mock_search.side_effect = Exception("API error")
        request = rf.post(f"/admin/courses/searchterm/{search_term.pk}/change/")
        request.user = admin_user
        request.session = {}
        request._messages = FallbackStorage(request)

        admin_instance = SearchTermAdmin(SearchTerm, None)
        admin_instance.test_search(request, search_term)

        messages_list = list(request._messages)
        info_messages = [m for m in messages_list if m.level == message_constants.INFO]
        assert not any("Executando busca" in str(m.message) for m in info_messages), (
            f"Found stale 'Executando busca' info message: {[m.message for m in info_messages]}"
        )

    @patch("infra.jobspy.service.JobSearchService.search")
    def test_stores_results_in_session_on_success(self, mock_search, rf, admin_user, search_term):
        """Successful search stores results in session."""
        from django.contrib.messages.storage.fallback import FallbackStorage

        from apps.courses.admin import SearchTermAdmin

        mock_search.return_value = [
            {"title": "Python Dev", "company": "Corp", "location": "Curitiba, PR"}
        ]
        request = rf.post(f"/admin/courses/searchterm/{search_term.pk}/change/")
        request.user = admin_user
        request.session = {}
        request._messages = FallbackStorage(request)

        admin_instance = SearchTermAdmin(SearchTerm, None)
        admin_instance.test_search(request, search_term)

        assert "job_search_results" in request.session
        assert len(request.session["job_search_results"]) == 1

    @patch("infra.jobspy.service.JobSearchService.search")
    def test_empty_results_shows_warning(self, mock_search, rf, admin_user, search_term):
        """Empty results should trigger a warning message."""
        from django.contrib.messages import constants as message_constants
        from django.contrib.messages.storage.fallback import FallbackStorage

        from apps.courses.admin import SearchTermAdmin

        mock_search.return_value = []
        request = rf.post(f"/admin/courses/searchterm/{search_term.pk}/change/")
        request.user = admin_user
        request.session = {}
        request._messages = FallbackStorage(request)

        admin_instance = SearchTermAdmin(SearchTerm, None)
        admin_instance.test_search(request, search_term)

        messages_list = list(request._messages)
        warning_messages = [m for m in messages_list if m.level == message_constants.WARNING]
        assert any("Nenhuma vaga" in str(m.message) for m in warning_messages), (
            f"Expected warning about no results, got: {[m.message for m in messages_list]}"
        )

    @patch("infra.jobspy.service.JobSearchService.search")
    def test_exception_shows_error_warning(self, mock_search, rf, admin_user, search_term):
        """Exception during search should trigger a warning message with the error."""
        from django.contrib.messages import constants as message_constants
        from django.contrib.messages.storage.fallback import FallbackStorage

        from apps.courses.admin import SearchTermAdmin

        mock_search.side_effect = Exception("API error")
        request = rf.post(f"/admin/courses/searchterm/{search_term.pk}/change/")
        request.user = admin_user
        request.session = {}
        request._messages = FallbackStorage(request)

        admin_instance = SearchTermAdmin(SearchTerm, None)
        admin_instance.test_search(request, search_term)

        messages_list = list(request._messages)
        warning_messages = [m for m in messages_list if m.level == message_constants.WARNING]
        assert any("Erro ao executar busca" in str(m.message) for m in warning_messages), (
            f"Expected error warning, got: {[m.message for m in messages_list]}"
        )


@pytest.mark.django_db
class TestSearchTermInline:
    def test_inline_has_simple_fields(self):
        from apps.courses.admin import SearchTermInline

        assert SearchTermInline.fields == ("term", "is_default", "priority")


@pytest.mark.django_db
class TestSearchUsesToSearchKwargs:
    """Verify admin test_search uses to_search_kwargs() — SSoT alignment."""

    @patch("infra.jobspy.service.JobSearchService.search")
    def test_test_search_calls_with_to_search_kwargs(
        self, mock_search, client, admin_user, search_term
    ):
        """test_search should call service.search with to_search_kwargs()."""
        mock_search.return_value = []
        client.force_login(admin_user)
        url = f"/admin/courses/searchterm/{search_term.pk}/change/"
        data = {
            ACTION_KEY: "1",
            "_save": "1",
            "course": search_term.course_id,
            "term": search_term.term,
            "is_default": "1",
            "priority": "0",
            "site_name": "linkedin,indeed,glassdoor",
            "location": "Curitiba, PR",
            "results_wanted": "10",
            "hours_old": "72",
            "country_indeed": "Brazil",
            "offset": "0",
            "is_remote": "0",
            "linkedin_fetch_description": "0",
        }
        client.post(url, data=data, follow=True)

        # Verify search was called with terms=[obj.term] and kwargs from to_search_kwargs()
        assert mock_search.called
        call_kwargs = mock_search.call_args[1]
        # Key fields from to_search_kwargs should be present
        assert "location" in call_kwargs
        assert "country_indeed" in call_kwargs
        assert "hours_old" in call_kwargs
