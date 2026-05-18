from datetime import date, timedelta
from unittest.mock import MagicMock

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


@pytest.mark.django_db
class TestFetchAndSaveDailyJobs:
    def setup_method(self):
        self.course = Course.objects.create(name="Engenharia de Software", is_active=True)
        self.search_term = SearchTerm.objects.create(
            course=self.course,
            term="python developer",
            is_default=True,
        )

    def _make_searcher(self, results):
        mock = MagicMock()
        mock.search.return_value = results
        return mock

    def test_persiste_vaga_com_job_url(self):
        from apps.jobs.models import DailyJob
        from apps.jobs.services import fetch_and_save_daily_jobs

        searcher = self._make_searcher([
            {"title": "Dev Python", "company": "Corp", "job_url": "https://example.com/1"},
        ])
        stats = fetch_and_save_daily_jobs(job_searcher=searcher)
        assert DailyJob.objects.filter(job_url="https://example.com/1").exists()
        assert DailyJob.objects.first().fetched_date == date.today()

    def test_filtra_vagas_sem_job_url(self):
        from apps.jobs.models import DailyJob
        from apps.jobs.services import fetch_and_save_daily_jobs

        searcher = self._make_searcher([
            {"title": "Sem URL", "company": "Corp", "job_url": None, "job_url_direct": None},
        ])
        fetch_and_save_daily_jobs(job_searcher=searcher)
        assert DailyJob.objects.count() == 0

    def test_aceita_job_url_direct_quando_job_url_vazio(self):
        from apps.jobs.models import DailyJob
        from apps.jobs.services import fetch_and_save_daily_jobs

        searcher = self._make_searcher([
            {
                "title": "Dev Java",
                "company": "Corp",
                "job_url": None,
                "job_url_direct": "https://example.com/direct/1",
            },
        ])
        fetch_and_save_daily_jobs(job_searcher=searcher)
        assert DailyJob.objects.filter(job_url="https://example.com/direct/1").exists()

    def test_idempotencia_bulk_create_ignore_conflicts(self):
        from apps.jobs.models import DailyJob
        from apps.jobs.services import fetch_and_save_daily_jobs

        searcher = self._make_searcher([
            {"title": "Dev Python", "company": "Corp", "job_url": "https://example.com/idem"},
        ])
        fetch_and_save_daily_jobs(job_searcher=searcher)
        fetch_and_save_daily_jobs(job_searcher=searcher)
        assert DailyJob.objects.filter(job_url="https://example.com/idem").count() == 1

    def test_retorna_dict_com_chaves_esperadas(self):
        from apps.jobs.services import fetch_and_save_daily_jobs

        searcher = self._make_searcher([
            {"title": "Dev", "company": "Corp", "job_url": "https://example.com/x"},
        ])
        stats = fetch_and_save_daily_jobs(job_searcher=searcher)
        assert set(stats.keys()) == {"terms_processed", "jobs_saved", "jobs_skipped", "errors"}

    def test_erro_em_termo_incrementa_errors_e_continua(self):
        from apps.courses.models import SearchTerm
        from apps.jobs.models import DailyJob
        from apps.jobs.services import fetch_and_save_daily_jobs

        # Cria segundo term para verificar que processamento continua após erro
        term2 = SearchTerm.objects.create(
            course=self.course, term="java developer", is_default=True
        )
        searcher = MagicMock()

        def side_effect(terms, **kwargs):
            if "python" in terms[0]:
                raise Exception("Scraping falhou")
            return [{"title": "Dev Java", "company": "Corp", "job_url": "https://example.com/j"}]

        searcher.search.side_effect = side_effect
        stats = fetch_and_save_daily_jobs(job_searcher=searcher)
        assert stats["errors"] == 1
        assert stats["terms_processed"] == 2
        assert DailyJob.objects.count() == 1

    def test_cria_job_search_log_com_user_none(self):
        from apps.jobs.models import JobSearchLog
        from apps.jobs.services import fetch_and_save_daily_jobs

        searcher = self._make_searcher([
            {"title": "Dev", "company": "Corp", "job_url": "https://example.com/log"},
        ])
        fetch_and_save_daily_jobs(job_searcher=searcher)
        assert JobSearchLog.objects.filter(user=None).count() == 1


@pytest.mark.django_db
class TestDailyJobCleanup:
    def setup_method(self):
        self.course = Course.objects.create(name="Ciência da Computação", is_active=True)
        self.search_term = SearchTerm.objects.create(
            course=self.course,
            term="machine learning",
            is_default=True,
        )

    def test_deleta_vagas_com_mais_de_7_dias(self):
        from apps.jobs.models import DailyJob
        from apps.jobs.services import fetch_and_save_daily_jobs

        old_date = date.today() - timedelta(days=8)
        DailyJob.objects.create(
            search_term=self.search_term,
            fetched_date=old_date,
            title="Vaga Antiga",
            company="Corp",
            job_url="https://example.com/old",
        )
        searcher = MagicMock()
        searcher.search.return_value = []
        fetch_and_save_daily_jobs(job_searcher=searcher)
        assert not DailyJob.objects.filter(job_url="https://example.com/old").exists()

    def test_nao_deleta_vagas_dentro_do_ttl(self):
        from apps.jobs.models import DailyJob
        from apps.jobs.services import fetch_and_save_daily_jobs

        recent_date = date.today() - timedelta(days=6)
        DailyJob.objects.create(
            search_term=self.search_term,
            fetched_date=recent_date,
            title="Vaga Recente",
            company="Corp",
            job_url="https://example.com/recent",
        )
        searcher = MagicMock()
        searcher.search.return_value = []
        fetch_and_save_daily_jobs(job_searcher=searcher)
        assert DailyJob.objects.filter(job_url="https://example.com/recent").exists()
