import json
import multiprocessing
import threading
import time
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest

from infra.jobspy.service import JobSearchService


@pytest.fixture
def service():
    return JobSearchService()


@pytest.fixture
def empty_df():
    return pd.DataFrame()


@pytest.fixture
def sample_df():
    return pd.DataFrame(
        {
            "title": ["Python Developer"],
            "company": ["Test Corp"],
            "location": ["Curitiba, PR"],
            "job_url": ["https://example.com/job/1"],
        }
    )


@pytest.mark.django_db
class TestJobSearchServiceNewParams:
    """Os kwargs são verificados na fronteira `_run_scrape` porque `scrape_jobs`
    passou a ser chamado no subprocesso — um mock patcheado aqui registra a
    chamada na memória do filho, invisível para o processo de teste."""

    @patch("infra.jobspy.service._run_scrape")
    def test_search_accepts_new_params(self, mock_run, service):
        mock_run.return_value = ("ok", [{"title": "Python Developer"}])
        result = service.search(
            terms=["python"],
            site_name=["linkedin"],
            country_indeed="Brazil",
            is_remote=False,
            offset=0,
        )
        assert result is not None
        scrape_kwargs = mock_run.call_args[0][0]
        assert scrape_kwargs["site_name"] == ["linkedin"]
        assert scrape_kwargs["country_indeed"] == "Brazil"
        assert scrape_kwargs["is_remote"] is False
        assert scrape_kwargs["offset"] == 0

    @patch("infra.jobspy.service._run_scrape")
    def test_search_backward_compatible(self, mock_run, service):
        mock_run.return_value = ("ok", [{"title": "Python Developer"}])
        result = service.search(terms=["python"])
        assert result is not None
        scrape_kwargs = mock_run.call_args[0][0]
        assert scrape_kwargs["site_name"] == ["linkedin", "indeed", "glassdoor"]

    @patch("infra.jobspy.service._run_scrape")
    def test_search_passes_site_name(self, mock_run, service):
        mock_run.return_value = ("ok", [])
        service.search(terms=["python"], site_name=["linkedin"])
        scrape_kwargs = mock_run.call_args[0][0]
        assert scrape_kwargs["site_name"] == ["linkedin"]

    @patch("infra.jobspy.service._run_scrape")
    def test_search_default_site_name(self, mock_run, service):
        mock_run.return_value = ("ok", [])
        service.search(terms=["python"], site_name=None)
        scrape_kwargs = mock_run.call_args[0][0]
        assert scrape_kwargs["site_name"] == ["linkedin", "indeed", "glassdoor"]

    @patch("infra.jobspy.service._run_scrape")
    def test_search_uses_default_timeout(self, mock_run, service):
        mock_run.return_value = ("ok", [])
        service.search(terms=["python"])
        assert mock_run.call_args[0][1] == JobSearchService.SEARCH_TIMEOUT_SECONDS

    @patch("infra.jobspy.service._run_scrape")
    def test_search_skips_term_on_error(self, mock_run, service):
        mock_run.return_value = ("error", "RuntimeError: boom")
        assert service.search(terms=["python"]) == []

    @patch("infra.jobspy.service._run_scrape")
    def test_search_survives_subprocess_start_failure(self, mock_run, service):
        # Falhar ao criar o subprocesso (fork sem memória, por exemplo) não pode
        # abortar os demais termos da busca.
        mock_run.side_effect = [
            OSError("Cannot allocate memory"),
            ("ok", [{"title": "Python Developer"}]),
        ]

        result = service.search(terms=["quebra", "python"])

        assert len(result) == 1
        assert result[0]["title"] == "Python Developer"


@pytest.mark.django_db
class TestJobSearchServiceTimeout:
    @patch("infra.jobspy.service.scrape_jobs")
    def test_search_returns_empty_when_scrape_hangs(self, mock_scrape, service):
        # Simula scrape_jobs preso (o scraper do LinkedIn entra em laço infinito
        # de paginação quando o termo não retorna vagas novas). search() deve
        # abortar no timeout e seguir adiante com lista vazia.
        def slow_scrape(*args, **kwargs):
            time.sleep(30.0)
            return pd.DataFrame()

        mock_scrape.side_effect = slow_scrape

        result = service.search(terms=["python"], timeout=1)

        assert result == []

    @patch("infra.jobspy.service.scrape_jobs")
    def test_search_continues_to_next_term_after_timeout(self, mock_scrape, service, sample_df):
        # Primeiro termo trava, segundo retorna normalmente. Resultado deve
        # conter apenas o segundo.
        def side_effect(*args, **kwargs):
            if kwargs.get("search_term") == "trava":
                time.sleep(30.0)
                return pd.DataFrame()
            return sample_df

        mock_scrape.side_effect = side_effect

        result = service.search(terms=["trava", "python"], timeout=1)

        assert len(result) == 1
        assert result[0]["title"] == "Python Developer"


@pytest.mark.django_db
class TestJobSearchServiceIsolation:
    """Regressão do incidente de produção: um scrape travado acumulava threads
    inabortáveis no worker Celery (~32/dia), saturando a CPU do host."""

    @patch("infra.jobspy.service.scrape_jobs")
    def test_hung_scrape_leaves_no_thread_behind(self, mock_scrape, service):
        def hang(*args, **kwargs):
            time.sleep(30.0)
            return pd.DataFrame()

        mock_scrape.side_effect = hang

        threads_before = threading.active_count()
        assert service.search(terms=["trava"], timeout=1) == []
        assert threading.active_count() == threads_before

    @patch("infra.jobspy.service.scrape_jobs")
    def test_hung_scrape_leaves_no_orphan_process(self, mock_scrape, service):
        def hang(*args, **kwargs):
            time.sleep(30.0)
            return pd.DataFrame()

        mock_scrape.side_effect = hang

        children_before = len(multiprocessing.active_children())
        assert service.search(terms=["trava"], timeout=1) == []
        assert len(multiprocessing.active_children()) == children_before

    @patch("infra.jobspy.service.scrape_jobs")
    def test_crash_in_subprocess_is_reported_as_error(self, mock_scrape, service):
        mock_scrape.side_effect = RuntimeError("scraper explodiu")

        assert service.search(terms=["python"]) == []

    @patch("infra.jobspy.service.scrape_jobs")
    def test_successful_search_leaves_no_orphan_process(self, mock_scrape, service, sample_df):
        mock_scrape.return_value = sample_df

        children_before = len(multiprocessing.active_children())
        result = service.search(terms=["python"])

        assert len(result) == 1
        assert len(multiprocessing.active_children()) == children_before


@pytest.mark.django_db
class TestJobSearchServiceJsonSafe:
    @patch("infra.jobspy.service.scrape_jobs")
    def test_search_results_are_json_serializable(self, mock_scrape, service):
        # Regressão: results são gravados em request.session no admin
        # (SearchTermAdmin.test_search). Django usa JSONSerializer por padrão,
        # então Timestamp, NaN e numpy scalars vindos de scrape_jobs precisam
        # estar normalizados antes de retornarem do service.
        mock_scrape.return_value = pd.DataFrame(
            {
                "title": ["Python Dev"],
                "company": ["Acme"],
                "date_posted": [pd.Timestamp("2026-04-26")],
                "salary": [np.nan],
                "applicants": [np.int64(42)],
            }
        )

        result = service.search(terms=["python"])

        # Deve ser serializável sem default=str
        json.dumps(result)

        record = result[0]
        assert isinstance(record["date_posted"], str)
        assert record["salary"] is None
        assert isinstance(record["applicants"], int)
