import time
from unittest.mock import patch

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
    @patch("infra.jobspy.service.scrape_jobs")
    def test_search_accepts_new_params(self, mock_scrape, service, sample_df):
        mock_scrape.return_value = sample_df
        result = service.search(
            terms=["python"],
            site_name=["linkedin"],
            country_indeed="Brazil",
            is_remote=False,
            offset=0,
        )
        assert result is not None
        call_kwargs = mock_scrape.call_args[1]
        assert call_kwargs["site_name"] == ["linkedin"]
        assert call_kwargs["country_indeed"] == "Brazil"
        assert call_kwargs["is_remote"] is False
        assert call_kwargs["offset"] == 0

    @patch("infra.jobspy.service.scrape_jobs")
    def test_search_backward_compatible(self, mock_scrape, service, sample_df):
        mock_scrape.return_value = sample_df
        result = service.search(terms=["python"])
        assert result is not None
        call_kwargs = mock_scrape.call_args[1]
        assert call_kwargs["site_name"] == ["linkedin", "indeed", "glassdoor"]

    @patch("infra.jobspy.service.scrape_jobs")
    def test_search_passes_site_name(self, mock_scrape, service, sample_df):
        mock_scrape.return_value = sample_df
        service.search(terms=["python"], site_name=["linkedin"])
        call_kwargs = mock_scrape.call_args[1]
        assert call_kwargs["site_name"] == ["linkedin"]

    @patch("infra.jobspy.service.scrape_jobs")
    def test_search_default_site_name(self, mock_scrape, service, sample_df):
        mock_scrape.return_value = sample_df
        service.search(terms=["python"], site_name=None)
        call_kwargs = mock_scrape.call_args[1]
        assert call_kwargs["site_name"] == ["linkedin", "indeed", "glassdoor"]


@pytest.mark.django_db
class TestJobSearchServiceTimeout:
    @patch("infra.jobspy.service.scrape_jobs")
    def test_search_returns_empty_when_scrape_hangs(self, mock_scrape, service):
        # Simula scrape_jobs preso em chamada C bloqueante: dorme bem mais que o
        # timeout. search() deve abortar via future.result(timeout=...) e seguir
        # adiante com lista vazia, garantindo que a task Celery finalize.
        def slow_scrape(*args, **kwargs):
            time.sleep(2.0)
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
                time.sleep(2.0)
                return pd.DataFrame()
            return sample_df

        mock_scrape.side_effect = side_effect

        result = service.search(terms=["trava", "python"], timeout=1)

        assert len(result) == 1
        assert result[0]["title"] == "Python Developer"
