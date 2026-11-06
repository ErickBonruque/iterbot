import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import structlog

from infra.adzuna.client import AdzunaClient, AdzunaError

logger = structlog.get_logger(__name__)

# Raiz do repositório (infra/jobspy/service.py -> infra/jobspy -> infra -> raiz).
# É o cwd do subprocesso, para que `python -m infra.jobspy._scrape_runner`
# encontre o pacote sem depender do PYTHONPATH herdado.
_PROJECT_ROOT = Path(__file__).resolve().parents[2]

# Módulo executado no subprocesso. Constante (e não literal inline) para que os
# testes possam apontar para um runner falso.
_RUNNER_MODULE = "infra.jobspy._scrape_runner"

# Quanto do stderr do subprocesso entra na mensagem de erro logada.
_STDERR_EXCERPT_CHARS = 500


def _failure_message(completed: subprocess.CompletedProcess) -> str:
    """Descreve um subprocesso que terminou sem devolver JSON no stdout.

    Cobre morte por sinal (OOM killer devolve returncode -9) e erro de
    importação antes do runner conseguir escrever qualquer coisa.
    """
    stderr = (completed.stderr or "").strip()
    excerpt = stderr[-_STDERR_EXCERPT_CHARS:] if stderr else "sem stderr"
    return f"runner encerrou com codigo {completed.returncode}: {excerpt}"


def _run_scrape(scrape_kwargs: dict[str, Any], timeout_seconds: float) -> tuple[str, Any]:
    """Roda `scrape_jobs` isolado em subprocesso, com timeout que de fato mata.

    O isolamento existe porque o python-jobspy pode entrar em laço infinito de
    paginação: o scraper do LinkedIn só avança o offset quando encontra vagas
    novas (`start += len(job_list)`), então uma busca sem resultados repete a
    mesma página para sempre. Uma thread nessa situação é inabortável e segue
    consumindo CPU até o processo morrer — foi o que saturou o worker em
    produção, acumulando ~32 threads por dia. Um processo separado, ao
    contrário, morre no SIGKILL do timeout levando junto os ThreadPoolExecutor
    que o jobspy abre por site.

    Usamos `subprocess` e não `multiprocessing`: a busca roda dentro de um
    ForkPoolWorker do Celery, que é um processo daemônico, e o multiprocessing
    proíbe filhos de daemon ("daemonic processes are not allowed to have
    children") — a tentativa anterior falhou em 100% dos termos em produção.

    O custo é subir um interpretador novo a cada termo (~1s local, alguns
    segundos no host de 1 vCPU por causa do import do pandas); `timeout_seconds`
    cobre startup + scrape.

    Returns:
        ("ok", records) em caso de sucesso, ("timeout", None) se estourou o
        tempo, ou ("error", mensagem) se o scrape falhou.
    """
    try:
        completed = subprocess.run(
            [sys.executable, "-m", _RUNNER_MODULE],
            input=json.dumps(scrape_kwargs),
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            cwd=_PROJECT_ROOT,
            check=False,
        )
    except subprocess.TimeoutExpired:
        # subprocess.run mata o filho (SIGKILL) e espera antes de propagar.
        return "timeout", None

    stdout = (completed.stdout or "").strip()
    if not stdout:
        return "error", _failure_message(completed)

    try:
        payload = json.loads(stdout)
    except ValueError:
        return "error", f"saida invalida do runner: {stdout[:_STDERR_EXCERPT_CHARS]}"

    if "error" in payload:
        return "error", payload["error"]

    if payload.get("board_errors"):
        # Site bloqueado (ex.: 429 do LinkedIn) devolve 0 vagas sem exceção —
        # sem este log, "bloqueado" e "dia sem vagas" ficam indistinguíveis.
        logger.warning(
            "jobspy_board_errors",
            term=scrape_kwargs.get("search_term"),
            board_errors=payload["board_errors"],
            board_warnings=payload.get("board_warnings"),
        )

    return "ok", payload.get("records", [])


ADZUNA_SITE = "adzuna"
DEFAULT_SITES = ["linkedin", "indeed", "glassdoor"]


def _default_adzuna_client() -> AdzunaClient:
    from config.adzuna_settings import AdzunaSettings

    adzuna = AdzunaSettings()
    return AdzunaClient(app_id=adzuna.app_id, app_key=adzuna.app_key, country=adzuna.country)


class JobSearchService:
    """Busca vagas em LinkedIn, Indeed e Glassdoor (python-jobspy) e na Adzuna.

    `site_name` escolhe as fontes de cada busca. "adzuna" é atendido pela API
    oficial (`infra.adzuna`), via HTTP direto — sem o subprocesso do jobspy,
    que só existe para conter o laço infinito do scraper do LinkedIn.
    """

    # Orçamento por termo incluindo o startup do subprocesso (ver `_run_scrape`).
    SEARCH_TIMEOUT_SECONDS = 40

    def __init__(self, adzuna_client: AdzunaClient | None = None) -> None:
        self._adzuna_client = adzuna_client

    @property
    def adzuna_client(self) -> AdzunaClient:
        if self._adzuna_client is None:
            self._adzuna_client = _default_adzuna_client()
        return self._adzuna_client

    def search(
        self,
        terms: list[str],
        location: str = "Curitiba, PR",
        limit: int = 10,
        hours_old: int = 72,
        site_name: list[str] | None = None,
        distance: int | None = None,
        job_type: str | None = None,
        is_remote: bool = False,
        country_indeed: str = "Brazil",
        linkedin_fetch_description: bool = False,
        linkedin_company_ids: list[int] | None = None,
        offset: int = 0,
        timeout: int | None = None,
    ) -> list[dict[str, Any]]:
        """Busca vagas para os termos fornecidos em multiplas plataformas.

        Cada termo roda em um subprocesso próprio (ver `_run_scrape`): um termo
        que trave não contamina os demais nem o worker Celery. Falha de uma
        fonte (timeout, bloqueio, Adzuna fora do ar) é logada e não impede as
        outras.

        Args:
            terms: Lista de termos de busca (ex: ["estagio python", "desenvolvedor junior"]).
            location: Localizacao geografica da busca.
            limit: Numero maximo de resultados por term.
            hours_old: Vagas publicadas nas ultimas N horas.
            site_name: Lista de sites para busca: linkedin, indeed, glassdoor,
                adzuna (default: linkedin, indeed, glassdoor).
            distance: Distancia em milhas do local de busca.
            job_type: Tipo de vaga (fulltime, parttime, internship, contract, temporary, other).
            is_remote: Filtrar apenas vagas remotas.
            country_indeed: Pais para busca no Indeed e Glassdoor.
            linkedin_fetch_description: Buscar descricao completa no LinkedIn.
            linkedin_company_ids: Lista de IDs de empresas no LinkedIn.
            offset: Offset para paginacao dos resultados.
            timeout: Tempo maximo em segundos para busca de cada termo (default: SEARCH_TIMEOUT_SECONDS).

        Returns:
            Lista de dicts com campos: title, company, location, job_type, job_url,
            date_posted, site.
        """
        timeout_seconds = timeout or self.SEARCH_TIMEOUT_SECONDS
        sites = site_name or DEFAULT_SITES
        jobspy_sites = [site for site in sites if site != ADZUNA_SITE]
        use_adzuna = ADZUNA_SITE in sites
        results = []

        for term in terms:
            if jobspy_sites:
                scrape_kwargs = self._build_scrape_kwargs(
                    term=term,
                    location=location,
                    limit=limit,
                    hours_old=hours_old,
                    site_name=jobspy_sites,
                    distance=distance,
                    job_type=job_type,
                    is_remote=is_remote,
                    country_indeed=country_indeed,
                    linkedin_fetch_description=linkedin_fetch_description,
                    linkedin_company_ids=linkedin_company_ids,
                    offset=offset,
                )
                results.extend(self._search_jobspy(term, location, scrape_kwargs, timeout_seconds))
            if use_adzuna:
                results.extend(
                    self._search_adzuna(
                        term,
                        location=location,
                        distance=distance,
                        is_remote=is_remote,
                        hours_old=hours_old,
                        limit=limit,
                    )
                )

        return results

    def _search_jobspy(
        self, term: str, location: str, scrape_kwargs: dict[str, Any], timeout_seconds: float
    ) -> list[dict[str, Any]]:
        """Um termo no jobspy, isolado em subprocesso. Falhas viram lista vazia."""
        try:
            status, payload = _run_scrape(scrape_kwargs, timeout_seconds)
        except Exception as exc:
            # Falha ao criar/conduzir o subprocesso (ex.: fork sem memória).
            # Um termo problemático não pode derrubar a busca inteira.
            logger.warning(
                "jobspy_search_failed",
                term=term,
                location=location,
                error=f"{type(exc).__name__}: {exc}",
            )
            return []

        if status == "timeout":
            logger.warning(
                "jobspy_search_timeout",
                term=term,
                location=location,
                timeout_seconds=timeout_seconds,
            )
            return []

        if status == "error":
            logger.warning(
                "jobspy_search_failed",
                term=term,
                location=location,
                error=payload,
            )
            return []

        records: list[dict[str, Any]] = payload
        logger.info("jobspy_search_success", term=term, count=len(records))
        return records

    def _search_adzuna(
        self,
        term: str,
        *,
        location: str,
        distance: int | None,
        is_remote: bool,
        hours_old: int,
        limit: int,
    ) -> list[dict[str, Any]]:
        """Um termo na Adzuna. Falhas (inclusive sem credencial) viram lista vazia."""
        try:
            records = self.adzuna_client.search(
                term,
                location=location,
                distance_miles=distance,
                is_remote=is_remote,
                hours_old=hours_old,
                limit=limit,
            )
        except AdzunaError as exc:
            logger.warning("adzuna_search_failed", term=term, location=location, error=str(exc))
            return []
        except Exception as exc:
            logger.warning(
                "adzuna_search_failed",
                term=term,
                location=location,
                error=f"{type(exc).__name__}: {exc}",
            )
            return []

        logger.info("adzuna_search_success", term=term, count=len(records))
        return records

    def _build_scrape_kwargs(
        self,
        term: str,
        location: str,
        limit: int,
        hours_old: int,
        site_name: list[str] | None,
        distance: int | None,
        job_type: str | None,
        is_remote: bool,
        country_indeed: str,
        linkedin_fetch_description: bool,
        linkedin_company_ids: list[int] | None,
        offset: int,
    ) -> dict[str, Any]:
        """Monta os kwargs de uma chamada a `scrape_jobs` para um termo."""
        return {
            "site_name": site_name or DEFAULT_SITES,
            "search_term": term,
            "location": location,
            "results_wanted": limit,
            "hours_old": hours_old,
            "country_indeed": country_indeed,
            "distance": distance,
            "job_type": job_type or None,
            "is_remote": is_remote,
            # Nome atual no jobspy 1.4 (`linkedin_fetch_description` é deprecated).
            # Busca a descrição de cada vaga nos sites cuja listagem não traz.
            "fetch_description": linkedin_fetch_description,
            "linkedin_company_ids": linkedin_company_ids,
            "offset": offset,
        }
