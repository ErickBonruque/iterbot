import json
import multiprocessing
import os
from typing import Any

import structlog
from jobspy import scrape_jobs

logger = structlog.get_logger(__name__)

# "fork" mantém a criação do subprocesso barata (copy-on-write) e preserva os
# patches que os testes aplicam em `scrape_jobs` no processo pai. O projeto roda
# exclusivamente em Linux (Docker), onde fork está sempre disponível.
#
# Forkar a partir de um processo com threads pode, em tese, travar o filho num
# lock herdado (o CPython emite DeprecationWarning nesse caso). Aceitamos o
# risco: a task roda no ForkPoolWorker do Celery, que é single-threaded, e um
# filho travado por qualquer motivo — deadlock ou laço infinito do jobspy — cai
# no mesmo timeout e é morto. Trocar para "forkserver"/"spawn" custaria reimportar
# o Django a cada termo e quebraria os mocks dos testes.
_MP_CONTEXT = multiprocessing.get_context("fork")

# Margem para o subprocesso encerrar após terminate() antes do kill() forçado.
_TERMINATE_GRACE_SECONDS = 2.0


def _records_from_dataframe(jobs_df) -> list[dict[str, Any]]:
    """Converte DataFrame em lista de dicts JSON-serializáveis.

    `jobs_df.to_dict("records")` preserva tipos pandas/numpy (Timestamp, NaN,
    int64, etc.) que não são compatíveis com `json.dumps` — quebra ao gravar
    em `request.session` (Django usa JSONSerializer por padrão desde 4.1) e
    em qualquer outra serialização downstream.

    Roteamos via `to_json(orient="records", date_format="iso")` que cuida da
    conversão (Timestamp → ISO string, NaN → null, numpy → tipos nativos).
    """
    if jobs_df is None or jobs_df.empty:
        return []
    return json.loads(jobs_df.to_json(orient="records", date_format="iso"))


def _scrape_worker(sender, scrape_kwargs: dict[str, Any]) -> None:
    """Executa `scrape_jobs` no processo filho e devolve o resultado pelo pipe.

    Encerra com `os._exit()` para pular atexit handlers e destrutores herdados
    do pai via fork — executá-los fecharia conexões de banco e do broker que o
    processo pai ainda está usando.
    """
    try:
        payload = ("ok", _records_from_dataframe(scrape_jobs(**scrape_kwargs)))
    except Exception as exc:
        payload = ("error", f"{type(exc).__name__}: {exc}")

    try:
        sender.send(payload)
        sender.close()
    except (BrokenPipeError, OSError):
        # O pai desistiu (timeout) e fechou a ponta dele — não há o que reportar.
        pass
    finally:
        os._exit(0)


def _terminate(proc) -> None:
    """Garante que o subprocesso morra, levando junto as threads do jobspy."""
    if proc.is_alive():
        proc.terminate()
        proc.join(_TERMINATE_GRACE_SECONDS)
    if proc.is_alive():
        proc.kill()
        proc.join(_TERMINATE_GRACE_SECONDS)
    try:
        proc.close()
    except ValueError:
        # Ainda não encerrou apesar do kill; os FDs saem com o processo.
        logger.warning("jobspy_subprocess_close_failed", pid=proc.pid)


def _run_scrape(scrape_kwargs: dict[str, Any], timeout_seconds: float) -> tuple[str, Any]:
    """Roda `scrape_jobs` isolado em subprocesso, com timeout que de fato mata.

    O isolamento existe porque o python-jobspy pode entrar em laço infinito de
    paginação: o scraper do LinkedIn só avança o offset quando encontra vagas
    novas (`start += len(job_list)`), então uma busca sem resultados repete a
    mesma página para sempre. Uma thread nessa situação é inabortável e segue
    consumindo CPU até o processo morrer — foi o que saturou o worker em
    produção, acumulando ~32 threads por dia. Um subprocesso, ao contrário,
    morre com terminate()/kill(), levando junto os ThreadPoolExecutor que o
    jobspy abre por site.

    Returns:
        ("ok", records) em caso de sucesso, ("timeout", None) se estourou o
        tempo, ou ("error", mensagem) se o scrape falhou.
    """
    receiver, sender = _MP_CONTEXT.Pipe(duplex=False)
    proc = _MP_CONTEXT.Process(
        target=_scrape_worker,
        args=(sender, scrape_kwargs),
        daemon=True,
    )
    proc.start()
    # O pai só lê: fechar a ponta de escrita aqui faz o recv() acusar EOF caso o
    # filho morra sem responder, em vez de bloquear até o timeout.
    sender.close()

    try:
        if not receiver.poll(timeout_seconds):
            return "timeout", None
        return receiver.recv()
    except EOFError:
        return "error", "subprocesso encerrou sem devolver resultado"
    finally:
        receiver.close()
        _terminate(proc)


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

        Cada termo roda em um subprocesso próprio (ver `_run_scrape`): um termo
        que trave não contamina os demais nem o worker Celery.

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
            scrape_kwargs = self._build_scrape_kwargs(
                term=term,
                location=location,
                limit=limit,
                hours_old=hours_old,
                site_name=site_name,
                distance=distance,
                job_type=job_type,
                is_remote=is_remote,
                country_indeed=country_indeed,
                linkedin_fetch_description=linkedin_fetch_description,
                linkedin_company_ids=linkedin_company_ids,
                offset=offset,
            )
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
                continue

            if status == "timeout":
                logger.warning(
                    "jobspy_search_timeout",
                    term=term,
                    location=location,
                    timeout_seconds=timeout_seconds,
                )
                continue

            if status == "error":
                logger.warning(
                    "jobspy_search_failed",
                    term=term,
                    location=location,
                    error=payload,
                )
                continue

            results.extend(payload)
            logger.info("jobspy_search_success", term=term, count=len(payload))

        return results

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
            "site_name": site_name or ["linkedin", "indeed", "glassdoor"],
            "search_term": term,
            "location": location,
            "results_wanted": limit,
            "hours_old": hours_old,
            "country_indeed": country_indeed,
            "distance": distance,
            "job_type": job_type or None,
            "is_remote": is_remote,
            "linkedin_fetch_description": linkedin_fetch_description,
            "linkedin_company_ids": linkedin_company_ids,
            "offset": offset,
        }
