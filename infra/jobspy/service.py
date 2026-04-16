from typing import Any

import structlog
from jobspy import scrape_jobs

logger = structlog.get_logger(__name__)


class JobSearchService:
    """Busca vagas em LinkedIn, Indeed e Glassdoor via python-jobspy."""

    def search(
        self,
        terms: list[str],
        location: str = "Curitiba, PR",
        limit: int = 10,
        hours_old: int = 72,
    ) -> list[dict[str, Any]]:
        """
        Busca vagas para os termos fornecidos em multiplas plataformas.

        Args:
            terms: Lista de termos de busca (ex: ["estagio python", "desenvolvedor junior"])
            location: Localizacao geografica da busca
            limit: Numero maximo de resultados por term
            hours_old: Vagas publicadas nas ultimas N horas

        Returns:
            Lista de dicts com campos: title, company, location, job_type, job_url, date_posted
        """
        results = []
        for term in terms:
            try:
                jobs_df = scrape_jobs(
                    site_name=["linkedin", "indeed", "glassdoor"],
                    search_term=term,
                    location=location,
                    results_wanted=limit,
                    hours_old=hours_old,
                    country_indeed="Brazil",
                )
                results.extend(jobs_df.to_dict("records"))
                logger.info("jobspy_search_success", term=term, count=len(jobs_df))
            except Exception as exc:
                logger.warning(
                    "jobspy_search_failed",
                    term=term,
                    location=location,
                    error=str(exc),
                )
                # Nao re-raise - continua para o proximo term
        return results
