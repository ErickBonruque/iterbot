from unittest.mock import patch

import pytest

from apps.jobs.models import ApplicationStatus, Job, JobApplication, JobStatus
from apps.jobs.tests.factories import CompanyFactory
from apps.users.models import StudentProfile, UserProfile


@pytest.fixture
def student(db):
    return UserProfile.objects.create(
        phone_number="5541999222333@c.us",
        ra="a1111111",
        email="aluno@alunos.utfpr.edu.br",
        is_authenticated_utfpr=True,
    )


@pytest.fixture
def job(db):
    company = CompanyFactory()
    return Job.objects.create(
        company=company,
        titulo="Vaga Teste",
        descricao="d",
        requisitos="r",
        tipo="Estágio",
        status=JobStatus.APPROVED,
    )


@pytest.mark.django_db
class TestJobApplicationModel:
    def test_defaults(self, student, job):
        application = JobApplication.objects.create(user=student, job=job)
        assert application.status == ApplicationStatus.PENDING
        assert application.message == ""
        assert application.profile_snapshot == {}

    def test_unique_per_user_job(self, student, job):
        JobApplication.objects.create(user=student, job=job)
        from django.db import IntegrityError

        with pytest.raises(IntegrityError):
            JobApplication.objects.create(user=student, job=job)


@pytest.mark.django_db
class TestStudentProfile:
    def test_is_complete(self, student):
        profile = StudentProfile.objects.create(user=student)
        assert profile.is_complete is False
        profile.periodo = "5º"
        profile.skills = "Python"
        assert profile.is_complete is True

    def test_to_snapshot(self, student):
        profile = StudentProfile.objects.create(
            user=student, periodo="5º", skills="Python", linkedin_url="https://linkedin.com/in/x"
        )
        snapshot = profile.to_snapshot()
        assert snapshot["periodo"] == "5º"
        assert snapshot["skills"] == "Python"
        assert snapshot["linkedin_url"] == "https://linkedin.com/in/x"
        assert snapshot["cv_url"] == ""


@pytest.mark.django_db
class TestJobApplicationEmail:
    def test_sends_email_to_company(self, student, job):
        application = JobApplication.objects.create(
            user=student,
            job=job,
            profile_snapshot={"periodo": "5º", "skills": "Python", "linkedin_url": "https://x.com"},
        )
        from apps.bot.email_service import send_job_application_email_to_company

        with patch("apps.bot.email_service.send_transactional_email") as mock_send:
            mock_send.return_value = {"status": "sent", "provider": "test", "message_id": "1"}
            result = send_job_application_email_to_company(application.id)

        assert result["status"] == "sent"
        kwargs = mock_send.call_args.kwargs
        assert kwargs["recipient_list"] == [job.company.email]
        assert "Python" in kwargs["message"]
        assert job.titulo in kwargs["subject"]

    def test_missing_application_returns_error(self, db):
        from apps.bot.email_service import send_job_application_email_to_company

        result = send_job_application_email_to_company(999999)
        assert result["status"] == "error"
        assert result["reason"] == "application_not_found"
