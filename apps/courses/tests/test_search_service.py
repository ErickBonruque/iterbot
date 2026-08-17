import io
import json
import os
import sys
import threading
import time
from contextlib import contextmanager
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest

from infra.jobspy import _scrape_runner, service as service_module
from infra.jobspy.records import records_from_dataframe
from infra.jobspy.service import JobSearchService


@pytest.fixture
def service():
    return JobSearchService()


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


@contextmanager
def fake_runner(tmp_path, body: str):
    """Substitui o runner real por um script controlado em `tmp_path`.

    `_run_scrape` executa `python -m <_RUNNER_MODULE>` com cwd `_PROJECT_ROOT`;
    apontando os dois para o script falso exercitamos o protocolo de verdade
    (JSON no stdin, JSON no stdout, kill no timeout) sem tocar a rede.
    """
    (tmp_path / "fake_runner.py").write_text(body)
    with (
        patch.dict(os.environ),
        patch.multiple(
            service_module,
            _PROJECT_ROOT=tmp_path,
            _RUNNER_MODULE="fake_runner",
        ),
    ):
        # O pytest-cov instrumenta subprocessos via COV_CORE_*/COVERAGE_PROCESS_*;
        # herdadas aqui, elas fazem o runner falso largar arquivos .coverage.*
        # órfãos no repo (ele roda com outro cwd, sem achar a config, e o combine
        # quebra ao juntar dados com e sem branch coverage).
        for key in [k for k in os.environ if k.startswith(("COV_CORE", "COVERAGE_"))]:
            del os.environ[key]
        yield


# Runner falso que devolve uma vaga fixa, ignorando os kwargs recebidos.
RUNNER_OK = """
import json, sys
json.load(sys.stdin)
json.dump({"records": [{"title": "Python Developer"}]}, sys.stdout)
"""

# Runner falso que trava — reproduz o laço infinito de paginação do LinkedIn.
RUNNER_HANGS = """
import time
time.sleep(60)
"""


class TestRunScrape:
    """Contrato entre `_run_scrape` e o processo runner."""

    def test_returns_records_from_runner(self, tmp_path):
        with fake_runner(tmp_path, RUNNER_OK):
            status, payload = service_module._run_scrape({"search_term": "python"}, 30)

        assert status == "ok"
        assert payload == [{"title": "Python Developer"}]

    def test_forwards_kwargs_through_stdin(self, tmp_path):
        # O runner devolve os kwargs que recebeu, provando que a serialização
        # de ida chegou íntegra do outro lado.
        with fake_runner(
            tmp_path,
            """
import json, sys
json.dump({"records": [json.load(sys.stdin)]}, sys.stdout)
""",
        ):
            status, payload = service_module._run_scrape(
                {"search_term": "python", "site_name": ["linkedin"]}, 30
            )

        assert status == "ok"
        assert payload == [{"search_term": "python", "site_name": ["linkedin"]}]

    def test_runner_error_payload_is_propagated(self, tmp_path):
        with fake_runner(
            tmp_path,
            """
import json, sys
json.dump({"error": "RuntimeError: scraper explodiu"}, sys.stdout)
""",
        ):
            status, payload = service_module._run_scrape({}, 30)

        assert status == "error"
        assert payload == "RuntimeError: scraper explodiu"

    def test_death_without_output_is_reported_as_error(self, tmp_path):
        # Cenário do OOM killer: o processo some sem escrever nada no stdout.
        with fake_runner(
            tmp_path,
            """
import os, sys
print("boom", file=sys.stderr)
os._exit(9)
""",
        ):
            status, payload = service_module._run_scrape({}, 30)

        assert status == "error"
        assert "codigo 9" in payload
        assert "boom" in payload

    def test_garbage_on_stdout_is_reported_as_error(self, tmp_path):
        with fake_runner(tmp_path, "print('nao sou json')"):
            status, payload = service_module._run_scrape({}, 30)

        assert status == "error"
        assert "saida invalida" in payload

    def test_timeout_reports_timeout(self, tmp_path):
        with fake_runner(tmp_path, RUNNER_HANGS):
            started = time.monotonic()
            status, payload = service_module._run_scrape({}, 1)
            elapsed = time.monotonic() - started

        assert (status, payload) == ("timeout", None)
        # Voltou no orçamento, não nos 60s do runner travado.
        assert elapsed < 15

    def test_timeout_actually_kills_the_runner(self, tmp_path):
        """Regressão do incidente de produção: um scrape travado seguia queimando
        CPU depois do timeout (thread inabortável dentro do worker Celery). O
        runner falso escreve num arquivo enquanto vive — se o arquivo continuar
        crescendo depois do timeout, o processo sobreviveu."""
        heartbeat = tmp_path / "heartbeat"
        with fake_runner(
            tmp_path,
            f"""
import time
with open({str(heartbeat)!r}, "a", buffering=1) as fh:
    while True:
        fh.write("tick\\n")
        time.sleep(0.05)
""",
        ):
            assert service_module._run_scrape({}, 1)[0] == "timeout"

        size_after_timeout = heartbeat.stat().st_size
        time.sleep(0.5)
        assert heartbeat.stat().st_size == size_after_timeout

    def test_hung_runner_leaves_no_thread_behind(self, tmp_path):
        threads_before = threading.active_count()

        with fake_runner(tmp_path, RUNNER_HANGS):
            assert service_module._run_scrape({}, 1)[0] == "timeout"

        assert threading.active_count() == threads_before


@pytest.mark.django_db
class TestJobSearchServiceParams:
    """Os kwargs são verificados na fronteira `_run_scrape` porque `scrape_jobs`
    roda no processo runner — um mock patcheado aqui registra a chamada na
    memória do filho, invisível para o processo de teste."""

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
    def test_search_skips_term_on_timeout(self, mock_run, service):
        mock_run.return_value = ("timeout", None)
        assert service.search(terms=["python"]) == []

    @patch("infra.jobspy.service._run_scrape")
    def test_search_continues_to_next_term_after_timeout(self, mock_run, service):
        mock_run.side_effect = [
            ("timeout", None),
            ("ok", [{"title": "Python Developer"}]),
        ]

        result = service.search(terms=["trava", "python"])

        assert len(result) == 1
        assert result[0]["title"] == "Python Developer"

    @patch("infra.jobspy.service._run_scrape")
    def test_search_survives_subprocess_start_failure(self, mock_run, service):
        # Falhar ao criar o subprocesso (sem memória, por exemplo) não pode
        # abortar os demais termos da busca.
        mock_run.side_effect = [
            OSError("Cannot allocate memory"),
            ("ok", [{"title": "Python Developer"}]),
        ]

        result = service.search(terms=["quebra", "python"])

        assert len(result) == 1
        assert result[0]["title"] == "Python Developer"


class TestScrapeRunner:
    """`_scrape_runner.main()` chamado no processo de teste, com o jobspy
    mockado — o que roda em produção é o mesmo código, só que via `python -m`."""

    def _run_main(self, monkeypatch, scrape_kwargs: dict) -> tuple[int, dict]:
        response = io.StringIO()
        monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(scrape_kwargs)))
        monkeypatch.setattr(sys, "stdout", response)

        code = _scrape_runner.main()

        return code, json.loads(response.getvalue())

    @patch("jobspy.scrape_jobs")
    def test_main_emits_records(self, mock_scrape, monkeypatch, sample_df):
        mock_scrape.return_value = sample_df

        code, payload = self._run_main(monkeypatch, {"search_term": "python"})

        assert code == 0
        assert payload["records"][0]["title"] == "Python Developer"
        assert mock_scrape.call_args.kwargs == {"search_term": "python"}

    @patch("jobspy.scrape_jobs")
    def test_main_reports_scrape_failure(self, mock_scrape, monkeypatch):
        mock_scrape.side_effect = RuntimeError("scraper explodiu")

        code, payload = self._run_main(monkeypatch, {"search_term": "python"})

        assert code == 1
        assert payload["error"] == "RuntimeError: scraper explodiu"

    @patch("jobspy.scrape_jobs")
    def test_main_keeps_stdout_clean(self, mock_scrape, monkeypatch, sample_df, capsys):
        # Uma lib que imprima no stdout não pode corromper a resposta JSON.
        def noisy_scrape(**kwargs):
            print("log solto do scraper")
            return sample_df

        mock_scrape.side_effect = noisy_scrape

        code, payload = self._run_main(monkeypatch, {"search_term": "python"})

        assert code == 0
        assert payload["records"][0]["title"] == "Python Developer"
        assert "log solto do scraper" in capsys.readouterr().err

    def test_main_reports_invalid_stdin(self, monkeypatch):
        response = io.StringIO()
        monkeypatch.setattr(sys, "stdin", io.StringIO("nao sou json"))
        monkeypatch.setattr(sys, "stdout", response)

        code = _scrape_runner.main()

        assert code == 1
        assert "kwargs invalidos" in json.loads(response.getvalue())["error"]


class TestRecordsFromDataframe:
    def test_records_are_json_serializable(self):
        # Regressão: results são gravados em request.session no admin
        # (SearchTermAdmin.test_search). Django usa JSONSerializer por padrão,
        # então Timestamp, NaN e numpy scalars vindos de scrape_jobs precisam
        # estar normalizados antes de chegarem ao service.
        records = records_from_dataframe(
            pd.DataFrame(
                {
                    "title": ["Python Dev"],
                    "company": ["Acme"],
                    "date_posted": [pd.Timestamp("2026-04-26")],
                    "salary": [np.nan],
                    "applicants": [np.int64(42)],
                }
            )
        )

        # Deve ser serializável sem default=str
        json.dumps(records)

        record = records[0]
        assert isinstance(record["date_posted"], str)
        assert record["salary"] is None
        assert isinstance(record["applicants"], int)

    def test_empty_dataframe_returns_empty_list(self):
        assert records_from_dataframe(pd.DataFrame()) == []

    def test_none_returns_empty_list(self):
        assert records_from_dataframe(None) == []
