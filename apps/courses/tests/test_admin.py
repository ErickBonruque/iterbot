import pytest
from django.contrib.admin.sites import AdminSite
from django.test import Client, RequestFactory
from unittest.mock import patch

from apps.courses.admin import SearchTermAdmin, ACTION_KEY
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

    User = get_user_model()
    return User.objects.create_superuser(
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
    def test_action_returns_results(self, mock_search, client, admin_user, search_term):
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
        response = client.post(url, data=data)
        assert response.status_code == 200

    @patch("infra.jobspy.service.JobSearchService.search")
    def test_action_empty_results(self, mock_search, client, admin_user, search_term):
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
        response = client.post(url, data=data)
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
        response = client.post(url, data=data)
        assert response.status_code == 200


@pytest.mark.django_db
class TestSearchTermInline:
    def test_inline_has_simple_fields(self):
        from apps.courses.admin import SearchTermInline

        assert SearchTermInline.fields == ("term", "is_default", "priority")