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
        st = SearchTerm.objects.create(
            course=course, term="python", distance=None
        )
        st.refresh_from_db()
        assert st.distance is None
