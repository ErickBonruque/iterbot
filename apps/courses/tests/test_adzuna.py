"""Cliente da Adzuna e o roteamento do site "adzuna" no JobSearchService."""

from unittest.mock import MagicMock, patch

import pytest
import requests

from infra.adzuna.client import (
    MAX_PAGES,
    AdzunaClient,
    AdzunaError,
    build_query,
    to_record,
)
from infra.jobspy.service import JobSearchService

APP_KEY = "segredo-123"


def adzuna_result(n: int = 1, **overrides):
    result = {
        "id": str(n),
        "title": f"Estágio em <strong>TI</strong> {n}",
        "company": {"display_name": "C.Vale"},
        "location": {"display_name": "Palotina, Paraná", "area": ["Brasil", "Sul"]},
        "redirect_url": f"https://www.adzuna.com.br/details/{n}",
        "description": "Suporte a <strong>sistemas</strong>…",
        "created": "2026-11-05T22:12:20Z",
        "contract_time": "part_time",
    }
    result.update(overrides)
    return result


def response(status=200, results=None, text=None):
    resp = MagicMock(status_code=status)
    resp.json.return_value = {"results": results or []}
    resp.text = text if text is not None else "{}"
    return resp


def client_with(*responses):
    session = MagicMock()
    session.get.side_effect = list(responses)
    return AdzunaClient("app-id", APP_KEY, session=session), session


class TestBuildQuery:
    def test_or_terms_become_what_or(self):
        query = build_query(
            "estágio OR estagiário",
            location="Brazil",
            distance_miles=None,
            is_remote=False,
            hours_old=None,
        )
        assert query["what_or"] == "estágio estagiário"
        assert "what" not in query

    def test_remote_adds_the_word_since_adzuna_has_no_remote_filter(self):
        query = build_query(
            "estágio OR estagiário",
            location="Brazil",
            distance_miles=None,
            is_remote=True,
            hours_old=None,
        )
        assert query["what"] == "remoto"

    def test_remote_word_is_not_repeated(self):
        query = build_query(
            "estágio dados remoto",
            location=None,
            distance_miles=None,
            is_remote=True,
            hours_old=None,
        )
        assert query["what"] == "estágio dados remoto"

    def test_country_only_location_means_whole_country(self):
        query = build_query(
            "estágio", location="Brazil", distance_miles=75, is_remote=False, hours_old=None
        )
        assert "where" not in query
        assert "distance" not in query

    def test_city_keeps_state_and_converts_miles_to_km(self):
        # Sem a UF, "Santa Helena" vira Santa Helena de SC na Adzuna.
        query = build_query(
            "estágio",
            location="Santa Helena, Paraná, Brazil",
            distance_miles=75,
            is_remote=False,
            hours_old=336,
        )
        assert query["where"] == "Santa Helena, Paraná"
        assert query["distance"] == 121
        assert query["max_days_old"] == 14
        assert query["sort_by"] == "date"


class TestToRecord:
    def test_maps_to_jobspy_shape_without_html(self):
        record = to_record(adzuna_result())
        assert record == {
            "site": "adzuna",
            "id": "adzuna-1",
            "title": "Estágio em TI 1",
            "company": "C.Vale",
            "location": "Palotina, Paraná",
            "job_url": "https://www.adzuna.com.br/details/1",
            "description": "Suporte a sistemas…",
            "date_posted": "2026-11-05T22:12:20Z",
            "job_type": "part_time",
            "is_remote": None,
        }

    def test_missing_company_and_location_become_empty(self):
        record = to_record(adzuna_result(company=None, location=None, contract_time=None))
        assert record["company"] == ""
        assert record["location"] == ""
        assert record["job_type"] == ""


class TestAdzunaClient:
    def test_single_page_when_limit_fits(self):
        client, session = client_with(response(results=[adzuna_result(1), adzuna_result(2)]))

        records = client.search("estágio", location="Santa Helena, PR", limit=50)

        assert [r["id"] for r in records] == ["adzuna-1", "adzuna-2"]
        url = session.get.call_args.args[0]
        params = session.get.call_args.kwargs["params"]
        assert url == "https://api.adzuna.com/v1/api/jobs/br/search/1"
        assert params["results_per_page"] == 50
        assert params["app_id"] == "app-id"

    def test_paginates_up_to_limit(self):
        full_page = [adzuna_result(i) for i in range(50)]
        client, session = client_with(response(results=full_page), response(results=full_page))

        records = client.search("estágio", limit=100)

        assert len(records) == 100
        assert session.get.call_count == 2

    def test_stops_when_a_page_is_not_full(self):
        client, session = client_with(response(results=[adzuna_result(1)]))
        client.search("estágio", limit=100)
        assert session.get.call_count == 1

    def test_page_cap_protects_monthly_quota(self):
        full_page = [adzuna_result(i) for i in range(50)]
        client, session = client_with(*[response(results=full_page)] * 10)
        client.search("estágio", limit=500)
        assert session.get.call_count == MAX_PAGES

    def test_missing_credentials_raise_without_calling_api(self):
        session = MagicMock()
        client = AdzunaClient("", "", session=session)
        with pytest.raises(AdzunaError, match="credenciais"):
            client.search("estágio")
        session.get.assert_not_called()

    def test_http_error_raises(self):
        client, _ = client_with(response(status=401, text="Unauthorised"))
        with pytest.raises(AdzunaError, match="HTTP 401"):
            client.search("estágio")

    def test_network_error_message_does_not_leak_the_key(self):
        session = MagicMock()
        session.get.side_effect = requests.ConnectionError(
            f"https://api.adzuna.com/...?app_key={APP_KEY}"
        )
        client = AdzunaClient("app-id", APP_KEY, session=session)
        with pytest.raises(AdzunaError) as exc_info:
            client.search("estágio")
        assert APP_KEY not in str(exc_info.value)

    def test_unexpected_payload_raises(self):
        bad = response()
        bad.json.side_effect = ValueError("not json")
        client, _ = client_with(bad)
        with pytest.raises(AdzunaError, match="inesperada"):
            client.search("estágio")


class TestServiceRouting:
    def adzuna_mock(self, records=None, error=None):
        adzuna = MagicMock()
        if error:
            adzuna.search.side_effect = error
        else:
            adzuna.search.return_value = records or []
        return adzuna

    @patch("infra.jobspy.service._run_scrape")
    def test_adzuna_is_not_sent_to_jobspy(self, mock_run):
        mock_run.return_value = ("ok", [{"title": "Indeed", "site": "indeed"}])
        adzuna = self.adzuna_mock([{"title": "Adzuna", "site": "adzuna"}])
        service = JobSearchService(adzuna_client=adzuna)

        results = service.search(
            terms=["estágio"],
            site_name=["indeed", "adzuna"],
            location="Santa Helena, PR",
            distance=75,
            is_remote=False,
            hours_old=336,
            limit=100,
        )

        assert [r["site"] for r in results] == ["indeed", "adzuna"]
        assert mock_run.call_args[0][0]["site_name"] == ["indeed"]
        adzuna.search.assert_called_once_with(
            "estágio",
            location="Santa Helena, PR",
            distance_miles=75,
            is_remote=False,
            hours_old=336,
            limit=100,
        )

    @patch("infra.jobspy.service._run_scrape")
    def test_adzuna_only_skips_the_scraper_subprocess(self, mock_run):
        service = JobSearchService(adzuna_client=self.adzuna_mock([{"title": "Adzuna"}]))
        assert service.search(terms=["estágio"], site_name=["adzuna"]) == [{"title": "Adzuna"}]
        mock_run.assert_not_called()

    @patch("infra.jobspy.service._run_scrape")
    def test_adzuna_failure_keeps_the_other_sites(self, mock_run):
        mock_run.return_value = ("ok", [{"title": "Indeed"}])
        service = JobSearchService(adzuna_client=self.adzuna_mock(error=AdzunaError("HTTP 429")))
        assert service.search(terms=["estágio"], site_name=["indeed", "adzuna"]) == [
            {"title": "Indeed"}
        ]

    @patch("infra.jobspy.service._run_scrape")
    def test_default_sites_do_not_call_adzuna(self, mock_run):
        mock_run.return_value = ("ok", [])
        adzuna = self.adzuna_mock()
        JobSearchService(adzuna_client=adzuna).search(terms=["estágio"])
        adzuna.search.assert_not_called()


def test_catalog_terms_use_adzuna():
    from apps.courses.catalog import COURSES

    sites = {row["site_name"] for course in COURSES for row in course["terms"]}
    assert all("adzuna" in s.split(",") for s in sites)
