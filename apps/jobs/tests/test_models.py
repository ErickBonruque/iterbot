import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from apps.jobs.tests.factories import CompanyFactory, JobFactory, JobApplicationFactory
from apps.jobs.models import CompanyStatus, JobStatus


@pytest.mark.django_db
class TestCompany:
    def test_company_creation(self):
        """Test Company model creation"""
        company = CompanyFactory()
        assert company.pk is not None
        assert company.status == CompanyStatus.APPROVED
    
    def test_company_cnpj_validation(self):
        """Test CNPJ validation"""
        company = CompanyFactory.build(cnpj="123")
        with pytest.raises(ValidationError) as exc_info:
            company.full_clean()
        assert 'cnpj' in exc_info.value.error_dict


@pytest.mark.django_db
class TestJob:
    def test_job_creation(self):
        """Test Job model creation"""
        job = JobFactory()
        assert job.pk is not None
        assert job.status == JobStatus.APPROVED
    
    def test_job_company_relationship(self):
        """Test Job belongs to Company"""
        job = JobFactory()
        assert job.company is not None
        assert job in job.company.jobs.all()


@pytest.mark.django_db
class TestJobApplication:
    def test_job_application_creation(self):
        """Test JobApplication creation"""
        application = JobApplicationFactory()
        assert application.pk is not None
    
    def test_job_application_unique_constraint(self):
        """Test unique constraint (user, job)"""
        application = JobApplicationFactory()
        with pytest.raises(IntegrityError):
            JobApplicationFactory(user=application.user, job=application.job)
