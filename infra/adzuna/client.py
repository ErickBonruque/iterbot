"""Cliente da API de busca de vagas da Adzuna (https://developer.adzuna.com).

Fonte complementar ao jobspy: é uma API oficial (JSON, sem scraping, sem
bloqueio por 429) que agrega anúncios de vários sites brasileiros e respeita
cidade + raio — cobre bem o Oeste do Paraná.

Devolve vagas no mesmo formato de dict do jobspy (title, company, location,
job_url, description...), para que o filtro de relevância, a deduplicação e o
"Testar busca" do admin tratem as duas fontes igual.

Particularidades da API medidas em nov/2026 (país `br`):

- `where="Santa Helena"` vira Santa Helena **de SC**; com a UF ("Santa Helena,
  PR") acerta o Paraná. Sufixo ", Brazil" é removido aqui.
- Não há filtro de "apenas remotas": a palavra "remoto" entra na busca e o
  filtro de relevância confere o texto da vaga.
- `what` exige todas as palavras; "a OR b" vira `what_or`.
- Algumas vagas vêm com o local geocodificado errado (Jacareí/SP aparece como
  Mato Grosso do Sul, dentro do raio de Santa Helena) — o filtro regional, que
  exige um município do Oeste do Paraná, descarta.
- Plano Trial: 1.500 chamadas/mês. Cada página (até 50 vagas) é uma chamada;
  os 12 termos do catálogo gastam no máximo 18 por coleta (~540/mês).
- A API às vezes devolve 503 (página HTML "Uh oh") por alguns segundos: erro
  5xx e de rede ganham UMA nova tentativa; 4xx (chave, cota) não.
"""

import math
import re
import time
from typing import Any

import requests

BASE_URL = "https://api.adzuna.com/v1/api/jobs/{country}/search/{page}"
MAX_RESULTS_PER_PAGE = 50
# Teto de páginas por termo: protege a cota mensal se alguém cadastrar
# `results_wanted` alto no admin.
MAX_PAGES = 2
MILES_TO_KM = 1.609344
# Uma nova tentativa para 5xx/erro de rede — barato na cota (≤ 1 chamada extra).
RETRY_DELAY_SECONDS = 3

_COUNTRY_SUFFIX = re.compile(r",?\s*\b(brazil|brasil)\s*$", re.IGNORECASE)
_OR_SPLIT = re.compile(r"\s+OR\s+")
_HTML_TAG = re.compile(r"<[^>]+>")


class AdzunaError(Exception):
    """Falha ao consultar a Adzuna (rede, credencial, cota ou resposta inválida)."""


def build_query(
    term: str,
    *,
    location: str | None,
    distance_miles: int | None,
    is_remote: bool,
    hours_old: int | None,
) -> dict[str, Any]:
    """Traduz os parâmetros de um SearchTerm para a query da Adzuna."""
    query: dict[str, Any] = {"sort_by": "date"}

    alternatives = [part.strip() for part in _OR_SPLIT.split(term) if part.strip()]
    if len(alternatives) > 1:
        query["what_or"] = " ".join(alternatives)
        what = ""
    else:
        what = term.strip()
    if is_remote and "remot" not in what.lower():
        what = f"{what} remoto".strip()
    if what:
        query["what"] = what

    where = _COUNTRY_SUFFIX.sub("", location or "").strip(" ,")
    if where:
        query["where"] = where
        if distance_miles:
            query["distance"] = round(distance_miles * MILES_TO_KM)

    if hours_old:
        query["max_days_old"] = max(1, math.ceil(hours_old / 24))
    return query


def to_record(result: dict[str, Any]) -> dict[str, Any]:
    """Converte um resultado da Adzuna no dict de vaga usado pelo resto do sistema."""
    description = _HTML_TAG.sub("", result.get("description") or "").strip()
    return {
        "site": "adzuna",
        "id": f"adzuna-{result.get('id')}",
        "title": _HTML_TAG.sub("", result.get("title") or "").strip(),
        "company": (result.get("company") or {}).get("display_name") or "",
        "location": (result.get("location") or {}).get("display_name") or "",
        "job_url": result.get("redirect_url") or "",
        "description": description,
        "date_posted": result.get("created"),
        "job_type": result.get("contract_time") or "",
        "is_remote": None,
    }


class AdzunaClient:
    """Busca vagas na Adzuna. Sem estado além das credenciais."""

    def __init__(
        self,
        app_id: str,
        app_key: str,
        country: str = "br",
        timeout_seconds: float = 20,
        session: requests.Session | None = None,
    ) -> None:
        self.app_id = app_id
        self.app_key = app_key
        self.country = country
        self.timeout_seconds = timeout_seconds
        self.session = session or requests.Session()

    @property
    def configured(self) -> bool:
        return bool(self.app_id and self.app_key)

    def search(
        self,
        term: str,
        *,
        location: str | None = None,
        distance_miles: int | None = None,
        is_remote: bool = False,
        hours_old: int | None = None,
        limit: int = MAX_RESULTS_PER_PAGE,
    ) -> list[dict[str, Any]]:
        """Busca até `limit` vagas (no máximo `MAX_PAGES` chamadas).

        Raises:
            AdzunaError: credencial ausente/recusada, cota estourada, erro de
                rede ou resposta fora do formato esperado.
        """
        if not self.configured:
            raise AdzunaError("credenciais ausentes (ADZUNA_APP_ID / ADZUNA_APP_KEY)")

        query = build_query(
            term,
            location=location,
            distance_miles=distance_miles,
            is_remote=is_remote,
            hours_old=hours_old,
        )
        wanted = max(1, limit)
        per_page = min(wanted, MAX_RESULTS_PER_PAGE)
        pages = min(MAX_PAGES, math.ceil(wanted / per_page))

        records: list[dict[str, Any]] = []
        for page in range(1, pages + 1):
            results = self._fetch_page(page, {**query, "results_per_page": per_page})
            records.extend(to_record(result) for result in results)
            if len(results) < per_page:
                break
        return records[:wanted]

    def _fetch_page(self, page: int, query: dict[str, Any]) -> list[dict[str, Any]]:
        try:
            return self._fetch_page_once(page, query)
        except _TransientError:
            time.sleep(RETRY_DELAY_SECONDS)
        try:
            return self._fetch_page_once(page, query)
        except _TransientError as exc:
            raise AdzunaError(str(exc)) from None

    def _fetch_page_once(self, page: int, query: dict[str, Any]) -> list[dict[str, Any]]:
        url = BASE_URL.format(country=self.country, page=page)
        params = {**query, "app_id": self.app_id, "app_key": self.app_key}
        try:
            response = self.session.get(url, params=params, timeout=self.timeout_seconds)
        except requests.RequestException as exc:
            # Mensagem sem a URL: ela carrega a app_key na query string.
            raise _TransientError(f"erro de rede: {type(exc).__name__}") from None

        if response.status_code != 200:
            message = f"HTTP {response.status_code}: {_short_text(response.text)}"
            if response.status_code >= 500:
                raise _TransientError(message)
            raise AdzunaError(message)
        try:
            results = response.json()["results"]
        except (ValueError, KeyError, TypeError):
            raise AdzunaError(f"resposta inesperada: {_short_text(response.text)}") from None
        if not isinstance(results, list):
            raise AdzunaError("resposta inesperada: 'results' não é lista")
        return results


class _TransientError(AdzunaError):
    """5xx ou falha de rede: vale tentar de novo."""


def _short_text(text: str) -> str:
    """Resumo do corpo para o log — sem tags (a página de erro da Adzuna é HTML)."""
    return " ".join(_HTML_TAG.sub(" ", text or "").split())[:120]
