from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from typing import Any

import structlog
from jobspy import scrape_jobs

logger = structlog.get_logger(__name__)


class JobSearchService:
    """Busca vagas em LinkedIn, Indeed e Glassdoor via python-jobspy.

    Attributes:
        None: This class is stateless; all config is passed to search().
    """

    SEARCH_TIMEOUT_SECONDS = 30

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

        Args:
            terms: Lista de termos de busca (ex: ["estagio python", "desenvolvedor junior"]).
            location: Localizacao geografica da busca.
            limit: Numero maximo de resultados por term.
            hours_old: Vagas publicadas nas ultimas N horas.
            site_name: Lista de sites para busca (default: linkedin, indeed, glassdoor).
            distance: Distancia em milhas do local de busca.
            job_type: Tipo de vaga (fulltime, parttime, internship, contract, temporary, other).
            is_remote: Filtrar apenas vagas remotas.
            country_indeed: Pais para busca no Indeed e Glassdoor.
            linkedin_fetch_description: Buscar descricao completa no LinkedIn.
            linkedin_company_ids: Lista de IDs de empresas no LinkedIn.
            offset: Offset para paginacao dos resultados.
            timeout: Tempo maximo em segundos para busca de cada termo (default: SEARCH_TIMEOUT_SECONDS).

        Returns:
            Lista de dicts com campos: title, company, location, job_type, job_url, date_posted.

        Raises:
            Exception: Logged and swallowed; search continues to next term.
        """
        timeout_seconds = timeout or self.SEARCH_TIMEOUT_SECONDS
        results = []
        for term in terms:
            # Usamos ThreadPoolExecutor por termo para garantir que future.result(timeout)
            # devolva o controle mesmo que `scrape_jobs` fique preso em chamadas C
            # bloqueantes (curl_cffi/urllib3) que ignoram signal.SIGALRM. A thread
            # daemon pode continuar rodando em background, mas a task Celery termina
            # e o worker fica livre para processar as próximas mensagens do bot.
            executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="jobspy-search")
            try:
                future = executor.submit(
                    scrape_jobs,
                    site_name=site_name or ["linkedin", "indeed", "glassdoor"],
                    search_term=term,
                    location=location,
                    results_wanted=limit,
                    hours_old=hours_old,
                    country_indeed=country_indeed,
                    distance=distance,
                    job_type=job_type or None,
                    is_remote=is_remote,
                    linkedin_fetch_description=linkedin_fetch_description,
                    linkedin_company_ids=linkedin_company_ids,
                    offset=offset,
                )
                try:
                    jobs_df = future.result(timeout=timeout_seconds)
                except FuturesTimeoutError:
                    logger.warning(
                        "jobspy_search_timeout",
                        term=term,
                        location=location,
                        timeout_seconds=timeout_seconds,
                    )
                    continue
                results.extend(jobs_df.to_dict("records"))
                logger.info("jobspy_search_success", term=term, count=len(jobs_df))
            except Exception as exc:
                logger.warning(
                    "jobspy_search_failed",
                    term=term,
                    location=location,
                    error=str(exc),
                )
            finally:
                # wait=False: não bloqueia o desligamento do executor; thread
                # eventualmente termina sozinha (ou é descartada no shutdown do
                # processo Celery). Disponível em Python 3.9+.
                executor.shutdown(wait=False, cancel_futures=True)
        return results
