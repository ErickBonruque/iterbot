from datetime import date

import pytest
from django.db import IntegrityError

from apps.courses.models import Course, SearchTerm


@pytest.mark.django_db
class TestDailyJobModel:
    def setup_method(self):
        self.course = Course.objects.create(name="Engenharia de Software", is_active=True)
        self.search_term = SearchTerm.objects.create(course=self.course, term="python")

    def test_create_daily_job(self):
        from apps.jobs.models import DailyJob

        job = DailyJob.objects.create(
            search_term=self.search_term,
            fetched_date=date.today(),
            title="Dev Python",
            company="Corp LTDA",
            job_url="https://example.com/vaga/1",
        )
        assert job.pk is not None

    def test_str_representation(self):
        from apps.jobs.models import DailyJob

        today = date.today()
        job = DailyJob.objects.create(
            search_term=self.search_term,
            fetched_date=today,
            title="Dev Python",
            company="Corp LTDA",
            job_url="https://example.com/vaga/2",
        )
        expected = f"Dev Python — Corp LTDA ({today})"
        assert str(job) == expected

    def test_verbose_name(self):
        from apps.jobs.models import DailyJob

        assert DailyJob._meta.verbose_name == "Vaga do Dia"

    def test_verbose_name_plural(self):
        from apps.jobs.models import DailyJob

        assert DailyJob._meta.verbose_name_plural == "Vagas do Dia"

    def test_is_manual_default_false(self):
        from apps.jobs.models import DailyJob

        job = DailyJob.objects.create(
            search_term=self.search_term,
            fetched_date=date.today(),
            title="Dev Python",
            company="Corp LTDA",
            job_url="https://example.com/vaga/3",
        )
        assert job.is_manual is False

    def test_optional_fields_blank_default(self):
        from apps.jobs.models import DailyJob

        job = DailyJob.objects.create(
            search_term=self.search_term,
            fetched_date=date.today(),
            title="Dev Python",
            company="Corp LTDA",
            job_url="https://example.com/vaga/4",
        )
        assert job.location == ""
        assert job.description == ""
        assert job.job_type == ""

    def test_index_fetched_date_search_term_declared(self):
        from apps.jobs.models import DailyJob

        index_fields = [
            list(idx.fields) for idx in DailyJob._meta.indexes
        ]
        assert ["fetched_date", "search_term"] in index_fields

    def test_index_search_term_fetched_date_declared(self):
        from apps.jobs.models import DailyJob

        index_fields = [
            list(idx.fields) for idx in DailyJob._meta.indexes
        ]
        assert ["search_term", "fetched_date"] in index_fields


@pytest.mark.django_db
class TestDailyJobUniqueness:
    def setup_method(self):
        self.course = Course.objects.create(name="Engenharia de Software", is_active=True)
        self.search_term = SearchTerm.objects.create(course=self.course, term="python")

    def test_unique_together_raises_on_duplicate(self):
        from apps.jobs.models import DailyJob

        today = date.today()
        DailyJob.objects.create(
            search_term=self.search_term,
            fetched_date=today,
            title="Dev Python",
            company="Corp LTDA",
            job_url="https://example.com/vaga/dup",
        )
        with pytest.raises(IntegrityError):
            DailyJob.objects.create(
                search_term=self.search_term,
                fetched_date=today,
                title="Dev Python 2",
                company="Outra Corp",
                job_url="https://example.com/vaga/dup",
            )

    def test_same_url_different_date_is_allowed(self):
        from apps.jobs.models import DailyJob
        from datetime import timedelta

        today = date.today()
        yesterday = today - timedelta(days=1)
        j1 = DailyJob.objects.create(
            search_term=self.search_term,
            fetched_date=today,
            title="Dev Python",
            company="Corp LTDA",
            job_url="https://example.com/vaga/reuse",
        )
        j2 = DailyJob.objects.create(
            search_term=self.search_term,
            fetched_date=yesterday,
            title="Dev Python",
            company="Corp LTDA",
            job_url="https://example.com/vaga/reuse",
        )
        assert j1.pk != j2.pk
