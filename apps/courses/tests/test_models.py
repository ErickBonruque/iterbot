import pytest
from django.core.exceptions import ValidationError

from apps.courses.models import Course, SearchTerm


@pytest.fixture
def course(db):
    return Course.objects.create(name="Engenharia de Software")


@pytest.mark.django_db
class TestSearchTermDefaults:
    def test_searchterm_defaults(self, course):
        st = SearchTerm.objects.create(course=course, term="python")
        assert st.site_name == "linkedin,indeed,glassdoor"
        assert st.location == "Curitiba, PR"
        assert st.results_wanted == 10
        assert st.hours_old == 72
        assert st.country_indeed == "Brazil"
        assert st.offset == 0
        assert st.is_remote is False
        assert st.linkedin_fetch_description is False
        assert st.distance is None
        assert st.job_type is None
        assert st.linkedin_company_ids is None


@pytest.mark.django_db
class TestSearchTermJobType:
    def test_searchterm_job_type_internship(self, course):
        st = SearchTerm.objects.create(course=course, term="estagio", job_type="internship")
        assert st.job_type == "internship"

    def test_searchterm_job_type_invalid(self, course):
        st = SearchTerm(course=course, term="test", job_type="invalid_type")
        with pytest.raises(ValidationError):
            st.full_clean()


@pytest.mark.django_db
class TestSearchTermCountryIndeed:
    def test_searchterm_country_brazil(self, course):
        st = SearchTerm.objects.create(course=course, term="python", country_indeed="Brazil")
        assert st.country_indeed == "Brazil"

    def test_searchterm_country_invalid(self, course):
        st = SearchTerm(course=course, term="test", country_indeed="InvalidCountry")
        with pytest.raises(ValidationError):
            st.full_clean()


@pytest.mark.django_db
class TestSearchTermLinkedinCompanyIds:
    def test_searchterm_linkedin_company_ids(self, course):
        st = SearchTerm.objects.create(
            course=course, term="python", linkedin_company_ids="123456,789012"
        )
        assert st.linkedin_company_ids == "123456,789012"


@pytest.mark.django_db
class TestSearchTermNullableFields:
    def test_searchterm_nullable_fields(self, course):
        st = SearchTerm.objects.create(course=course, term="python", distance=None)
        st.refresh_from_db()
        assert st.distance is None


@pytest.mark.django_db
class TestSearchTermToSearchKwargs:
    def test_to_search_kwargs_propagates_full_config(self, course):
        # Regressão: bot ignorava location/is_remote/job_type/etc. e usava
        # defaults do JobSearchService — divergindo do "Testar busca" do admin.
        st = SearchTerm.objects.create(
            course=course,
            term="cientista de dados",
            site_name="linkedin,indeed",
            location="Brasil",
            distance=100,
            job_type="fulltime",
            is_remote=True,
            results_wanted=10,
            hours_old=168,
            country_indeed="Brazil",
            linkedin_fetch_description=True,
            linkedin_company_ids="123,456",
            offset=5,
        )

        kwargs = st.to_search_kwargs()

        assert kwargs == {
            "location": "Brasil",
            "limit": 10,
            "hours_old": 168,
            "site_name": ["linkedin", "indeed"],
            "distance": 100,
            "job_type": "fulltime",
            "is_remote": True,
            "country_indeed": "Brazil",
            "linkedin_fetch_description": True,
            "linkedin_company_ids": [123, 456],
            "offset": 5,
        }

    def test_to_search_kwargs_limit_override(self, course):
        st = SearchTerm.objects.create(course=course, term="python", results_wanted=20)
        assert st.to_search_kwargs(limit_override=5)["limit"] == 5

    def test_to_search_kwargs_blank_job_type_becomes_none(self, course):
        st = SearchTerm.objects.create(course=course, term="python", job_type="")
        assert st.to_search_kwargs()["job_type"] is None

    def test_to_search_kwargs_invalid_company_ids_returns_none(self, course):
        st = SearchTerm.objects.create(course=course, term="python", linkedin_company_ids="abc,def")
        assert st.to_search_kwargs()["linkedin_company_ids"] is None
