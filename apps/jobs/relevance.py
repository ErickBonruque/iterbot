"""Filtro de relevância das vagas online (jobspy) para os alunos de Santa Helena.

A busca online devolve muito ruído: vagas dos EUA (LinkedIn não entende
"Brasil"), "Jovem Aprendiz", vendedor, estágio de outra área. Buscar mais não
resolve — na região quase não há estágio específico por curso. A qualidade vem
de classificar cada vaga depois da busca, com duas regras de produto:

- **regional**: estágio presencial no Oeste do Paraná, da área do curso;
- **remoto**: estágio ou vaga de nível inicial remota, da área do curso — algo
  que o aluno consiga conciliar com a graduação.

"Da área do curso" = palavra-chave do curso no título, ou o nome do curso
citado na descrição ("cursando Ciência da Computação"). As palavras-chave e os
nomes ficam no cadastro do curso (admin), não aqui.

Funções puras, sem Django: testáveis isoladamente e reaproveitáveis pelo admin.
"""

import re
import unicodedata
from collections.abc import Iterable
from typing import Any

REGIONAL = "regional"
REMOTE = "remoto"

# Municípios do Oeste do Paraná até ~120 km de Santa Helena — o raio que o
# aluno consegue conciliar com as aulas presenciais.
OESTE_PARANA = (
    "santa helena",
    "cascavel",
    "toledo",
    "foz do iguacu",
    "medianeira",
    "marechal candido rondon",
    "palotina",
    "assis chateaubriand",
    "sao miguel do iguacu",
    "santa terezinha de itaipu",
    "missal",
    "itaipulandia",
    "ceu azul",
    "matelandia",
    "vera cruz do oeste",
    "ramilandia",
    "diamante do oeste",
    "sao jose das palmeiras",
    "entre rios do oeste",
    "pato bragado",
    "mercedes",
    "guaira",
    "terra roxa",
    "nova santa rosa",
    "quatro pontes",
    "maripa",
    "ouro verde do oeste",
    "sao pedro do iguacu",
    "tupassi",
    "cafelandia",
    "corbelia",
    "santa tereza do oeste",
)

# Siglas de UF que não colidem com estados dos EUA (AL, MA, MS, MT, PA e SC
# colidem: "Boston, MA" não pode virar Maranhão).
_BR_UF = "ac|ap|am|ba|ce|df|es|go|mg|pb|pr|pe|pi|rj|rn|rs|ro|rr|sp|se|to"
_BR_MARKERS = re.compile(
    r"brazil|brasil|\bremoto\b|"
    r"parana|sao paulo|rio de janeiro|minas gerais|santa catarina|rio grande do (sul|norte)|"
    r"goias|bahia|pernambuco|ceara|espirito santo|mato grosso|distrito federal|amazonas|"
    r"paraiba|piaui|maranhao|alagoas|sergipe|tocantins|rondonia|roraima|amapa|acre|"
    r"greater (sao paulo|rio de janeiro|curitiba|belo horizonte|porto alegre|florianopolis|"
    r"campinas|brasilia|recife|salvador|fortaleza)|"
    rf",\s*({_BR_UF})\b"
)
_REGION = re.compile(r"\b(" + "|".join(OESTE_PARANA) + r")\b")

_INTERNSHIP = re.compile(r"\bestagi|\binterns?\b|\binternship")
_ENTRY_LEVEL = re.compile(
    r"\b(junior|jr|trainee|iniciante|meio periodo|part[- ]?time|freela\w*|freelancer)\b"
)
_EXCLUDED = re.compile(
    r"\b(aprendiz|senior|sr|pleno|lead|lider|gerente|coordenador\w*|especialista|"
    r"supervisor\w*|diretor\w*|professor\w*|docente|vendedor\w*|tecnico de enfermagem)\b"
)
_REMOTE_SIGNAL = re.compile(
    r"\bremot\w*|\bhome ?office\b|\bteletrabalho\b|\b100% online\b|\banywhere\b"
)
_NOT_REMOTE = re.compile(r"\b(hibrid\w*|hybrid|presencial)\b")

# Quanto da descrição ler atrás de "remoto": o começo traz o modelo de
# trabalho; o resto costuma ser texto institucional que gera falso positivo.
_REMOTE_DESCRIPTION_CHARS = 400


def normalize(text: Any) -> str:
    """Minúsculas, sem acento e com espaços colapsados ("Estágio" -> "estagio")."""
    if text is None:
        return ""
    ascii_text = unicodedata.normalize("NFKD", str(text)).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", ascii_text).strip().lower()


def parse_terms(raw: str | None) -> list[str]:
    """Lista de termos de um campo de texto do admin (um por linha ou por vírgula)."""
    terms: list[str] = []
    for chunk in re.split(r"[\n,;]", raw or ""):
        term = normalize(chunk)
        if term and term not in terms:
            terms.append(term)
    return terms


def _keyword_pattern(keyword: str) -> re.Pattern:
    # Casa no início de palavra ("desenvolv" pega "desenvolvedora"); siglas
    # curtas exigem a palavra inteira, senão "ti" casaria com "tiago".
    suffix = r"\b" if len(keyword) <= 3 else ""
    return re.compile(rf"\b{re.escape(keyword)}{suffix}")


def _mentions_any(text: str, terms: Iterable[str]) -> bool:
    return any(_keyword_pattern(term).search(text) for term in terms)


def _has_brazil_marker(location: str) -> bool:
    return bool(_BR_MARKERS.search(location))


def is_in_brazil(location: Any) -> bool:
    """Local brasileiro ou não informado (vaga remota costuma vir sem local)."""
    loc = normalize(location)
    if loc in ("", "nan", "none"):
        return True
    return _has_brazil_marker(loc)


def is_in_region(location: Any) -> bool:
    """Cidade do Oeste do Paraná — e no Brasil ("Toledo, Spain" não conta)."""
    loc = normalize(location)
    return bool(_REGION.search(loc)) and _has_brazil_marker(loc)


def _scope_rejection(
    scope: str, *, title: str, location: Any, description: str, flagged_remote: bool
) -> str | None:
    """Regras de local e nível de cada escopo. None = passou."""
    is_internship = bool(_INTERNSHIP.search(title))
    if scope == REGIONAL:
        if not is_in_region(location):
            return "fora_regiao"
        if not is_internship:
            return "nao_estagio"
    elif scope == REMOTE:
        if _NOT_REMOTE.search(title):
            return "nao_remoto"
        remote_text = f"{title} {normalize(location)} {description[:_REMOTE_DESCRIPTION_CHARS]}"
        if not (flagged_remote or _REMOTE_SIGNAL.search(remote_text)):
            return "nao_remoto"
        if not (is_internship or _ENTRY_LEVEL.search(title)):
            return "nivel"
    return None


def classify(
    record: dict[str, Any],
    *,
    title_keywords: list[str],
    course_names: list[str],
    scope: str,
    board_remote: bool = False,
) -> str:
    """Decide se a vaga serve ao curso. Devolve "ok" ou o motivo da recusa.

    Args:
        record: Vaga como veio do jobspy (title, location, description...).
        title_keywords: Palavras-chave da área do curso, já normalizadas.
        course_names: Nomes do curso aceitos na descrição, já normalizados.
        scope: REGIONAL ou REMOTE.
        board_remote: O site aplicou o filtro de remoto na busca (Indeed
            aplica; LinkedIn ignora — aí só vale o que o texto disser).

    Returns:
        "ok", ou um motivo: excluido, fora_brasil, fora_regiao, nao_estagio,
        nao_remoto, nivel, fora_area. O motivo vai para os logs para medir o
        filtro em produção. Sem palavras-chave nem nomes, a área não é exigida.
    """
    title = normalize(record.get("title"))
    description = normalize(record.get("description"))
    location = record.get("location")

    if _EXCLUDED.search(title):
        return "excluido"
    if not is_in_brazil(location):
        return "fora_brasil"

    rejection = _scope_rejection(
        scope,
        title=title,
        location=location,
        description=description,
        flagged_remote=board_remote or bool(record.get("is_remote")),
    )
    if rejection:
        return rejection

    if not (title_keywords or course_names):
        # Curso sem palavras-chave cadastradas: filtra local e nível, mas não a
        # área — melhor mostrar estágio genérico do que nada.
        return "ok"
    if _mentions_any(title, title_keywords) or _mentions_any(description, course_names):
        return "ok"
    return "fora_area"


def dedupe(
    records: list[dict[str, Any]], max_per_company: int | None = None
) -> list[dict[str, Any]]:
    """Remove a mesma vaga repetida entre sites e cidades.

    - mesmo título + empresa: a BairesDev publica a mesma vaga em 20 cidades;
    - mesmo título + cidade: Indeed e Glassdoor trazem a vaga com nomes de
      empresa diferentes. Fica a versão com descrição (o Glassdoor não traz),
      que é a que o filtro de área consegue ler.

    `max_per_company` limita quantas vagas uma empresa ocupa na lista.
    """
    kept: list[dict[str, Any]] = []
    index_by_key: dict[tuple[str, str], int] = {}

    for record in records:
        title = normalize(record.get("title"))
        company_key = (title, normalize(record.get("company")))
        city_key = (title, normalize(str(record.get("location") or "").split(",")[0]))
        existing = index_by_key.get(company_key, index_by_key.get(city_key))
        if existing is not None:
            if record.get("description") and not kept[existing].get("description"):
                kept[existing] = record
            continue
        index_by_key[company_key] = index_by_key[city_key] = len(kept)
        kept.append(record)

    if max_per_company is None:
        return kept

    per_company: dict[str, int] = {}
    capped = []
    for record in kept:
        company = normalize(record.get("company"))
        per_company[company] = per_company.get(company, 0) + 1
        if per_company[company] <= max_per_company:
            capped.append(record)
    return capped
