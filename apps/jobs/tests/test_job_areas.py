import pytest

from apps.courses.models import Area
from apps.jobs.models import Job
from apps.jobs.tests.factories import CompanyFactory, JobFactory


@pytest.fixture
def area_ti(db):
    return Area.objects.create(name="Área Job TI")


@pytest.fixture
def area_eng(db):
    return Area.objects.create(name="Área Job Eng")


@pytest.fixture
def company(db):
    """Empresa única reutilizada — CompanyFactory tem CNPJ fixo (unique)."""
    return CompanyFactory()


@pytest.mark.django_db
class TestJobForArea:
    def test_job_with_matching_area_is_returned(self, area_ti):
        job = JobFactory()
        job.areas.add(area_ti)
        assert list(Job.objects.for_area(area_ti)) == [job]

    def test_job_with_other_area_is_excluded(self, area_ti, area_eng):
        job = JobFactory()
        job.areas.add(area_eng)
        assert list(Job.objects.for_area(area_ti)) == []

    def test_job_without_areas_counts_as_all(self, area_ti):
        """Convenção travada: vaga sem nenhuma área = ofertada para todas."""
        job = JobFactory()  # sem áreas
        assert list(Job.objects.for_area(area_ti)) == [job]

    def test_job_with_multiple_areas_no_duplicates(self, area_ti, area_eng):
        job = JobFactory()
        job.areas.add(area_ti, area_eng)
        result = list(Job.objects.for_area(area_ti))
        assert result == [job]  # distinct() evita duplicatas pelo join M2M

    def test_for_area_none_returns_only_universal_jobs(self, area_ti, company):
        universal = JobFactory(company=company)  # sem áreas
        targeted = JobFactory(company=company)
        targeted.areas.add(area_ti)
        result = list(Job.objects.for_area(None))
        assert universal in result
        assert targeted not in result

    def test_for_area_combines_matching_and_universal(self, area_ti, area_eng, company):
        universal = JobFactory(company=company)
        ti_job = JobFactory(company=company)
        ti_job.areas.add(area_ti)
        eng_job = JobFactory(company=company)
        eng_job.areas.add(area_eng)
        result = set(Job.objects.for_area(area_ti))
        assert result == {universal, ti_job}
