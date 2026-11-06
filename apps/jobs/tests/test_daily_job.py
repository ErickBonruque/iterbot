from datetime import date, timedelta
from unittest.mock import MagicMock, patch

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

        index_fields = [list(idx.fields) for idx in DailyJob._meta.indexes]
        assert ["fetched_date", "search_term"] in index_fields

    def test_index_search_term_fetched_date_declared(self):
        from apps.jobs.models import DailyJob

        index_fields = [list(idx.fields) for idx in DailyJob._meta.indexes]
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

        searcher = self._make_searcher(
            [
                {"title": "Dev Python", "company": "Corp", "job_url": "https://example.com/1"},
            ]
        )
        fetch_and_save_daily_jobs(job_searcher=searcher)
        assert DailyJob.objects.filter(job_url="https://example.com/1").exists()
        assert DailyJob.objects.first().fetched_date == date.today()

    def test_grava_a_fonte_da_vaga(self):
        from apps.jobs.models import DailyJob
        from apps.jobs.services import fetch_and_save_daily_jobs

        searcher = self._make_searcher(
            [
                {"title": "A", "company": "X", "job_url": "https://e.com/1", "site": "adzuna"},
                {"title": "B", "company": "Y", "job_url": "https://e.com/2", "site": "indeed"},
                {"title": "C", "company": "Z", "job_url": "https://e.com/3"},
            ]
        )
        fetch_and_save_daily_jobs(job_searcher=searcher)
        sources = dict(DailyJob.objects.values_list("title", "source"))
        assert sources == {"A": "adzuna", "B": "indeed", "C": ""}

    def test_filtra_vagas_sem_job_url(self):
        from apps.jobs.models import DailyJob
        from apps.jobs.services import fetch_and_save_daily_jobs

        searcher = self._make_searcher(
            [
                {"title": "Sem URL", "company": "Corp", "job_url": None, "job_url_direct": None},
            ]
        )
        fetch_and_save_daily_jobs(job_searcher=searcher)
        assert DailyJob.objects.count() == 0

    def test_aceita_job_url_direct_quando_job_url_vazio(self):
        from apps.jobs.models import DailyJob
        from apps.jobs.services import fetch_and_save_daily_jobs

        searcher = self._make_searcher(
            [
                {
                    "title": "Dev Java",
                    "company": "Corp",
                    "job_url": None,
                    "job_url_direct": "https://example.com/direct/1",
                },
            ]
        )
        fetch_and_save_daily_jobs(job_searcher=searcher)
        assert DailyJob.objects.filter(job_url="https://example.com/direct/1").exists()

    def test_idempotencia_bulk_create_ignore_conflicts(self):
        from apps.jobs.models import DailyJob
        from apps.jobs.services import fetch_and_save_daily_jobs

        searcher = self._make_searcher(
            [
                {"title": "Dev Python", "company": "Corp", "job_url": "https://example.com/idem"},
            ]
        )
        fetch_and_save_daily_jobs(job_searcher=searcher)
        fetch_and_save_daily_jobs(job_searcher=searcher)
        assert DailyJob.objects.filter(job_url="https://example.com/idem").count() == 1

    def test_retorna_dict_com_chaves_esperadas(self):
        from apps.jobs.services import fetch_and_save_daily_jobs

        searcher = self._make_searcher(
            [
                {"title": "Dev", "company": "Corp", "job_url": "https://example.com/x"},
            ]
        )
        stats = fetch_and_save_daily_jobs(job_searcher=searcher)
        assert set(stats.keys()) == {
            "terms_processed",
            "terms_empty",
            "jobs_found",
            "jobs_filtered",
            "jobs_saved",
            "jobs_skipped",
            "errors",
        }

    def test_erro_em_termo_incrementa_errors_e_continua(self):
        from apps.courses.models import SearchTerm
        from apps.jobs.models import DailyJob
        from apps.jobs.services import fetch_and_save_daily_jobs

        # Cria segundo term para verificar que processamento continua após erro
        SearchTerm.objects.create(course=self.course, term="java developer", is_default=True)
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

    def test_persiste_vaga_com_campos_nulos_do_scraper(self):
        from apps.jobs.models import DailyJob
        from apps.jobs.services import fetch_and_save_daily_jobs

        # Regressão de produção: o jobspy devolve None nas colunas que não
        # preencheu (description vem sempre nula sem linkedin_fetch_description)
        # e os campos do modelo são NOT NULL — um registro assim derrubava o
        # bulk_create do termo inteiro com IntegrityError.
        searcher = self._make_searcher(
            [
                {
                    "title": "Dev Python",
                    "company": "Corp",
                    "location": None,
                    "description": None,
                    "job_type": None,
                    "job_url": "https://example.com/nulo",
                },
            ]
        )

        stats = fetch_and_save_daily_jobs(job_searcher=searcher)

        job = DailyJob.objects.get(job_url="https://example.com/nulo")
        assert (job.description, job.location, job.job_type) == ("", "", "")
        assert stats["errors"] == 0
        assert stats["jobs_saved"] == 1

    def test_trunca_campos_maiores_que_a_coluna(self):
        from apps.jobs.models import DailyJob
        from apps.jobs.services import fetch_and_save_daily_jobs

        searcher = self._make_searcher(
            [
                {
                    "title": "T" * 300,
                    "company": "Corp",
                    "job_url": "https://example.com/longo",
                },
            ]
        )

        fetch_and_save_daily_jobs(job_searcher=searcher)

        assert len(DailyJob.objects.get(job_url="https://example.com/longo").title) == 255

    def test_conta_termo_sem_resultado_em_terms_empty(self):
        from apps.jobs.services import fetch_and_save_daily_jobs

        stats = fetch_and_save_daily_jobs(job_searcher=self._make_searcher([]))

        assert stats["terms_empty"] == 1
        assert stats["jobs_saved"] == 0

    def test_vaga_repetida_conta_como_skipped_e_nao_como_salva(self):
        from apps.jobs.services import fetch_and_save_daily_jobs

        searcher = self._make_searcher(
            [
                {"title": "Dev", "company": "Corp", "job_url": "https://example.com/dup"},
            ]
        )
        fetch_and_save_daily_jobs(job_searcher=searcher)

        stats = fetch_and_save_daily_jobs(job_searcher=searcher)

        assert stats["jobs_saved"] == 0
        assert stats["jobs_skipped"] == 1

    def test_cria_job_search_log_com_user_none(self):
        from apps.jobs.models import JobSearchLog
        from apps.jobs.services import fetch_and_save_daily_jobs

        searcher = self._make_searcher(
            [
                {"title": "Dev", "company": "Corp", "job_url": "https://example.com/log"},
            ]
        )
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


class TestFetchDailyJobsTask:
    def test_task_registrada_na_celery_app(self):
        from waha_bot.celery import app

        assert "apps.jobs.tasks.fetch_daily_jobs" in app.tasks

    def test_beat_schedule_contem_fetch_daily_jobs(self):
        from django.conf import settings

        assert "fetch-daily-jobs" in settings.CELERY_BEAT_SCHEDULE

    def test_beat_schedule_horario_7h_sem_day_of_week(self):
        from celery.schedules import crontab
        from django.conf import settings

        entry = settings.CELERY_BEAT_SCHEDULE["fetch-daily-jobs"]
        schedule = entry["schedule"]
        assert isinstance(schedule, crontab)
        # crontab.hour e .minute são sets internamente — verificar via _orig_hour/_orig_minute
        # ou comparar com outro crontab equivalente
        expected = crontab(hour=7, minute=0)
        assert schedule.hour == expected.hour
        assert schedule.minute == expected.minute
        # Sem restrição de dia da semana — roda todo dia (day_of_week="*")
        assert schedule.day_of_week == expected.day_of_week

    def test_beat_schedule_aponta_para_task_correta(self):
        from django.conf import settings

        entry = settings.CELERY_BEAT_SCHEDULE["fetch-daily-jobs"]
        assert entry["task"] == "apps.jobs.tasks.fetch_daily_jobs"


@pytest.mark.django_db
class TestDailyJobAdmin:
    def setup_method(self):
        from apps.courses.models import Course, SearchTerm

        self.course = Course.objects.create(name="Engenharia de Software", is_active=True)
        self.search_term = SearchTerm.objects.create(course=self.course, term="python")

    def test_dailyjob_registrado_no_admin(self):
        from django.contrib import admin

        from apps.jobs.models import DailyJob

        assert DailyJob in admin.site._registry

    def test_list_display_contem_campos_esperados(self):
        from django.contrib import admin

        from apps.jobs.models import DailyJob

        daily_job_admin = admin.site._registry[DailyJob]
        for field in ("title", "company", "search_term", "fetched_date", "is_manual"):
            assert field in daily_job_admin.list_display, f"Campo '{field}' ausente em list_display"

    def test_list_filter_contem_campos_esperados(self):
        from django.contrib import admin

        from apps.jobs.models import DailyJob

        daily_job_admin = admin.site._registry[DailyJob]
        for field in ("fetched_date", "is_manual"):
            assert field in daily_job_admin.list_filter, f"Campo '{field}' ausente em list_filter"

    def test_search_fields_contem_title_e_company(self):
        from django.contrib import admin

        from apps.jobs.models import DailyJob

        daily_job_admin = admin.site._registry[DailyJob]
        assert "title" in daily_job_admin.search_fields
        assert "company" in daily_job_admin.search_fields

    def test_date_hierarchy_e_fetched_date(self):
        from django.contrib import admin

        from apps.jobs.models import DailyJob

        daily_job_admin = admin.site._registry[DailyJob]
        assert daily_job_admin.date_hierarchy == "fetched_date"

    def test_actions_submit_line_contem_mark_as_manual(self):
        from django.contrib import admin

        from apps.jobs.models import DailyJob

        daily_job_admin = admin.site._registry[DailyJob]
        assert "mark_as_manual" in daily_job_admin.actions_submit_line

    def test_mark_as_manual_atualiza_is_manual_para_true(self):
        from datetime import date

        from django.contrib import admin

        from apps.jobs.models import DailyJob

        job = DailyJob.objects.create(
            search_term=self.search_term,
            fetched_date=date.today(),
            title="Dev Python",
            company="Corp LTDA",
            job_url="https://example.com/admin-test/1",
            is_manual=False,
        )
        daily_job_admin = admin.site._registry[DailyJob]
        request = MagicMock()
        daily_job_admin.mark_as_manual(request, job)
        job.refresh_from_db()
        assert job.is_manual is True


@pytest.mark.django_db
class TestFetchRelevanceFilter:
    """O filtro de relevância roda antes de salvar: o aluno só vê vaga útil."""

    def setup_method(self):
        self.course = Course.objects.create(
            name="Agronomia",
            job_title_keywords="agronomia, agricola",
            job_course_names="agronomia",
        )
        self.regional = SearchTerm.objects.create(
            course=self.course,
            term="estágio",
            scope="regional",
            site_name="indeed",
            location="Santa Helena, PR",
        )

    def _searcher(self, results):
        mock = MagicMock()
        mock.search.return_value = results
        return mock

    def _job(self, title, location="Cascavel, PR, Brazil", n=1):
        return {
            "title": title,
            "company": f"C{n}",
            "location": location,
            "job_url": f"https://example.com/{n}",
            "site": "indeed",
        }

    def test_only_relevant_jobs_are_saved(self):
        from apps.jobs.models import DailyJob
        from apps.jobs.services import fetch_and_save_daily_jobs

        results = [
            self._job("Estagiário de Agronomia", n=1),
            self._job("Estágio - Agência Sicredi", n=2),  # fora da área
            self._job("Jovem Aprendiz Agrícola", n=3),  # excluído
            self._job("Estágio Agronomia", "Sarandi, Paraná, Brazil", n=4),  # fora da região
        ]

        stats = fetch_and_save_daily_jobs(self._searcher(results))

        titles = list(DailyJob.objects.values_list("title", flat=True))
        assert titles == ["Estagiário de Agronomia"]
        assert stats["jobs_found"] == 4
        assert stats["jobs_filtered"] == 3

    def test_identical_searches_run_once_per_day(self):
        # Busca regional ampla é igual nos três cursos: um scrape só
        from apps.jobs.services import fetch_and_save_daily_jobs

        other = Course.objects.create(name="Ciências Biológicas", job_title_keywords="biologia")
        SearchTerm.objects.create(
            course=other,
            term="estágio",
            scope="regional",
            site_name="indeed",
            location="Santa Helena, PR",
        )
        searcher = self._searcher([self._job("Estágio em Biologia", n=9)])

        fetch_and_save_daily_jobs(searcher)

        assert searcher.search.call_count == 1

    def test_filter_emptying_a_term_is_not_a_scraper_failure(self):
        # "fetch_daily_jobs_no_results" é alarme de scraper quebrado; vagas
        # recusadas pelo filtro não podem disparar isso
        from apps.jobs.services import fetch_and_save_daily_jobs

        with patch("apps.jobs.services.logger") as mock_logger:
            stats = fetch_and_save_daily_jobs(
                self._searcher([self._job("Estágio - Agência Sicredi")])
            )

        assert stats["jobs_saved"] == 0
        events = [c.args[0] for c in mock_logger.error.call_args_list]
        assert "fetch_daily_jobs_no_results" not in events

    def test_term_without_scope_keeps_everything(self):
        from apps.jobs.models import DailyJob
        from apps.jobs.services import fetch_and_save_daily_jobs

        self.regional.scope = ""
        self.regional.save()

        fetch_and_save_daily_jobs(self._searcher([self._job("Vendedor Interno")]))

        assert DailyJob.objects.count() == 1
