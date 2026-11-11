"""Testes dos serviços de vagas: review sob demanda e resumo semanal."""

from datetime import date, timedelta
from unittest.mock import patch

import pytest

from apps.courses.models import Area, Course, SearchTerm
from apps.jobs.models import DailyJob
from apps.jobs.services import build_review_for_user


@pytest.mark.django_db
class TestBuildReviewForUser:
    """ "Ver Review" lê as vagas pré-buscadas — nada de scraping com o aluno esperando."""

    @pytest.fixture
    def course(self):
        return Course.objects.create(name="Agronomia")

    def _daily(self, term, title, n, fetched=None):
        return DailyJob.objects.create(
            search_term=term,
            fetched_date=fetched or date.today(),
            title=title,
            company=f"Empresa {n}",
            location="Cascavel, PR, Brazil",
            job_url=f"https://example.com/{n}",
        )

    def test_uses_latest_fetch_ordered_by_term_priority(self, course):
        low = SearchTerm.objects.create(course=course, term="remoto", priority=1)
        high = SearchTerm.objects.create(course=course, term="regional", priority=10)
        self._daily(low, "Estágio remoto", 1)
        self._daily(high, "Estágio na região", 2)
        self._daily(high, "Vaga velha", 3, fetched=date.today() - timedelta(days=2))

        titles = [j["title"] for j in build_review_for_user(course)]

        assert titles == ["Estágio na região", "Estágio remoto"]

    def test_same_job_from_two_terms_appears_once(self, course):
        a = SearchTerm.objects.create(course=course, term="a", priority=2)
        b = SearchTerm.objects.create(course=course, term="b", priority=1)
        self._daily(a, "Estagiário de Agronomia", 1)
        DailyJob.objects.create(
            search_term=b,
            fetched_date=date.today(),
            title="Estagiário de Agronomia",
            company="Empresa 1",
            location="Cascavel, PR, Brazil",
            job_url="https://example.com/1",
        )

        assert len(build_review_for_user(course)) == 1

    def test_local_company_jobs_come_first(self, course):
        term = SearchTerm.objects.create(course=course, term="a")
        self._daily(term, "Estágio online", 1)
        local = {"title": "Vaga da empresa parceira", "company": "Coop"}

        with patch("apps.jobs.services.get_local_jobs_for_area", return_value=[local]):
            jobs = build_review_for_user(course)

        assert jobs[0] == local
        assert jobs[1]["title"] == "Estágio online"

    def test_limits_to_five(self, course):
        term = SearchTerm.objects.create(course=course, term="a")
        for n in range(8):
            self._daily(term, f"Estágio {n}", n)
        assert len(build_review_for_user(course)) == 5

    def test_no_jobs_returns_empty(self, course):
        assert build_review_for_user(course) == []


@pytest.mark.django_db
@pytest.mark.django_db
class TestLocalAreaReview:
    """Testes dos helpers de review semanal local por área (Fase 2)."""

    @pytest.fixture
    def area(self):
        return Area.objects.create(name="Área Review Local")

    @pytest.fixture
    def course(self, area):
        return Course.objects.create(name="Curso Review Local", area=area)

    def test_get_local_jobs_for_area_returns_matching_and_universal(self, area, settings):
        from apps.jobs.models import JobStatus
        from apps.jobs.services import get_local_jobs_for_area
        from apps.jobs.tests.factories import CompanyFactory, JobFactory

        settings.PORTAL_BASE_URL = "https://portal.example.com"
        company = CompanyFactory()
        targeted = JobFactory(company=company, status=JobStatus.APPROVED)
        targeted.areas.add(area)
        universal = JobFactory(company=company, status=JobStatus.APPROVED)  # sem áreas

        result = get_local_jobs_for_area(area)
        titles = {j["title"] for j in result}
        assert titles == {targeted.titulo, universal.titulo}
        assert all(j["source"] == "local" for j in result)

    def test_get_local_jobs_for_area_excludes_non_approved(self, area, settings):
        from apps.jobs.models import JobStatus
        from apps.jobs.services import get_local_jobs_for_area
        from apps.jobs.tests.factories import CompanyFactory, JobFactory

        settings.PORTAL_BASE_URL = "https://portal.example.com"
        company = CompanyFactory()
        pending = JobFactory(company=company, status=JobStatus.PENDING)
        pending.areas.add(area)

        assert get_local_jobs_for_area(area) == []

    def test_build_weekly_local_review_uses_course_area(self, course, area, settings):
        from apps.jobs.models import JobStatus
        from apps.jobs.services import build_weekly_local_review
        from apps.jobs.tests.factories import CompanyFactory, JobFactory

        settings.PORTAL_BASE_URL = "https://portal.example.com"
        job = JobFactory(company=CompanyFactory(), status=JobStatus.APPROVED)
        job.areas.add(area)

        result = build_weekly_local_review(course)
        assert [j["title"] for j in result] == [job.titulo]

    def test_build_weekly_local_review_course_without_area(self, settings):
        """Curso sem área → só vagas 'para todas'."""
        from apps.jobs.models import JobStatus
        from apps.jobs.services import build_weekly_local_review
        from apps.jobs.tests.factories import CompanyFactory, JobFactory

        settings.PORTAL_BASE_URL = "https://portal.example.com"
        course = Course.objects.create(name="Curso Sem Área Review")
        company = CompanyFactory()
        universal = JobFactory(company=company, status=JobStatus.APPROVED)  # sem áreas

        other_area = Area.objects.create(name="Outra Área Review")
        targeted = JobFactory(company=company, status=JobStatus.APPROVED)
        targeted.areas.add(other_area)

        result = build_weekly_local_review(course)
        assert [j["title"] for j in result] == [universal.titulo]

    def test_format_weekly_local_review_message_has_local_header(self):
        from apps.jobs.services import format_weekly_local_review_message

        msg = format_weekly_local_review_message(
            "Engenharia", [{"title": "Dev", "company": "ACME"}]
        )
        assert "Vagas locais — Engenharia" in msg
        assert "*1. Dev* — ACME" in msg


@pytest.mark.django_db
class TestLocalJobLink:
    def test_link_da_vaga_local_aponta_para_pagina_publica(self, settings):
        from apps.jobs.services import _serialize_local_job
        from apps.jobs.tests.factories import JobFactory

        settings.PORTAL_BASE_URL = "https://portal.example"
        job = JobFactory()

        job_url = _serialize_local_job(job)["job_url"]

        assert job_url == f"https://portal.example/vagas/{job.pk}/"
        assert "/empresas/" not in job_url
