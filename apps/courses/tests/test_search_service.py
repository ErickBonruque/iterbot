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
