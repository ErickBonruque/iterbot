"""Catálogo de cursos e termos de busca do campus Santa Helena — fonte única.

Usado pelo comando `seed_courses` (instalação nova) e pela migração
`0006_apply_course_catalog` (produção). Antes havia três cópias divergentes
(comando, fixture JSON e o banco), e o LinkedIn recebia "Brasil", que ele não
entende e troca por resultados dos EUA.

Os termos foram escolhidos medindo, em buscas reais (nov/2026), quantas vagas
*relevantes e inéditas* cada um traz depois do filtro de `apps.jobs.relevance`:

- **regional**: uma busca ampla ("estágio") no Indeed num raio de 75 milhas
  (~120 km) de Santa Helena — cobre Cascavel, Toledo, Foz, Medianeira e MCR —
  e o filtro separa por curso. Termos específicos no Indeed regional voltam
  vazios; o LinkedIn ignora a cidade, então ele só entra nos termos de
  agronomia/biologia, com o filtro de região descartando o resto do país.
  Glassdoor ficou de fora: devolve as mesmas vagas do Indeed, sem descrição.
- **remoto**: o Indeed respeita "apenas remotas"; o LinkedIn não (a palavra
  "remoto" no termo e o texto da vaga fazem esse papel).
- **Adzuna** (API oficial, `infra/adzuna`) entra em todos os termos: respeita
  cidade + raio e traz vagas que o Indeed não tem (cooperativas do Oeste, por
  exemplo). Na medição de nov/2026 somou 3 estágios regionais (CC 2, BIO 1) e
  3 remotos de CC. Custa ~9 chamadas/dia de uma cota de 2.500/mês.

Termos iguais em cursos diferentes (a busca regional e a remota amplas) rodam
uma vez só por dia — `fetch_and_save_daily_jobs` reaproveita o resultado.
"""

from typing import Any

REGION_SHORT = "Santa Helena, PR"  # formato aceito por Indeed e Glassdoor
REGION_LONG = "Santa Helena, Paraná, Brazil"  # LinkedIn também entende
REGION_RADIUS_MILES = 75

_REGIONAL_BROAD = {
    "term": "estágio",
    "label": "Estágios na região",
    "scope": "regional",
    "site_name": "indeed,adzuna",
    "location": REGION_SHORT,
    "distance": REGION_RADIUS_MILES,
    "is_remote": False,
    "results_wanted": 100,
    "hours_old": 336,
    "priority": 10,
}

_REMOTE_BROAD = {
    "term": "estágio OR estagiário",
    "label": "Estágios remotos",
    "scope": "remoto",
    "site_name": "indeed,adzuna",
    "location": "Brazil",
    "distance": None,
    "is_remote": True,
    "results_wanted": 100,
    "hours_old": 168,
    "priority": 5,
}


def _remote(term: str, label: str, priority: int) -> dict[str, Any]:
    return {
        "term": term,
        "label": label,
        "scope": "remoto",
        "site_name": "linkedin,indeed,adzuna",
        "location": "Brazil",
        "distance": None,
        "is_remote": True,
        "results_wanted": 50,
        "hours_old": 168,
        "priority": priority,
    }


def _regional(term: str, label: str, priority: int) -> dict[str, Any]:
    return {
        "term": term,
        "label": label,
        "scope": "regional",
        "site_name": "linkedin,indeed,adzuna",
        "location": REGION_LONG,
        "distance": REGION_RADIUS_MILES,
        "is_remote": False,
        "results_wanted": 50,
        "hours_old": 336,
        "priority": priority,
    }


COURSES: list[dict[str, Any]] = [
    {
        "code": "COENS",
        "name": "Ciência da Computação",
        "area_code": "ti",
        "order": 1,
        "job_title_keywords": (
            "desenvolv, programacao, programador, software, sistemas, dados, data, ti, "
            "tecnologia da informacao, suporte tecnico, infraestrutura, devops, cloud, "
            "frontend, front-end, backend, back-end, full stack, fullstack, qa, tester, "
            "testes de software, web, mobile, python, java, javascript, react, node, "
            "banco de dados, bi, business intelligence, seguranca da informacao, "
            "ciberseguranca, inteligencia artificial, ia, machine learning, computacao, "
            "automacao, rpa, analista de sistemas"
        ),
        "job_course_names": (
            "ciencia da computacao, ciencias da computacao, sistemas de informacao, "
            "engenharia de software, engenharia da computacao, "
            "analise e desenvolvimento de sistemas"
        ),
        "terms": [
            {**_REGIONAL_BROAD},
            {**_REMOTE_BROAD, "priority": 9},
            _remote("estágio desenvolvedor remoto", "Estágio em desenvolvimento (remoto)", 8),
            _remote("estágio dados remoto", "Estágio em dados (remoto)", 7),
            _remote("desenvolvedor júnior remoto", "Desenvolvimento júnior (remoto)", 6),
        ],
    },
    {
        "code": "COAGR",
        "name": "Agronomia",
        "area_code": "agro-bio",
        "order": 2,
        "job_title_keywords": (
            "agronom, agricol, agricultura, agronegocio, agro, fitossanidade, fitotecnia, "
            "solos, sementes, graos, lavoura, plantio, producao vegetal, defensivos, "
            "insumos agricolas, irrigacao, pecuaria, zootecnia, horticultura, florestal, "
            "extensao rural, assistencia tecnica agricola"
        ),
        "job_course_names": "agronomia, engenharia agronomica, ciencias agrarias",
        "terms": [
            {**_REGIONAL_BROAD},
            _regional("estágio agronomia", "Estágio em agronomia", 9),
            {**_REMOTE_BROAD},
        ],
    },
    {
        "code": "COBIO",
        "name": "Ciências Biológicas",
        "area_code": "agro-bio",
        "order": 3,
        "job_title_keywords": (
            "biolog, biotecn, microbiolog, laborator, analises clinicas, meio ambiente, "
            "ambiental, ecolog, genet, botanic, zoolog, bioquim, vigilancia sanitaria, "
            "saneamento, aquicultura, piscicultura, limnolog, herbario, licenciamento, "
            "educacao ambiental"
        ),
        "job_course_names": "ciencias biologicas, biologia",
        "terms": [
            {**_REGIONAL_BROAD},
            _regional("estágio biologia", "Estágio em biologia", 9),
            _regional("estágio meio ambiente", "Estágio em meio ambiente", 8),
            {**_REMOTE_BROAD},
        ],
    },
]

_COURSE_DEFAULTS = {"level": "Graduação", "modality": "Presencial", "is_active": True}


def apply_catalog(
    course_model, term_model, area_model, *, create_missing: bool, prune: bool
) -> dict[str, int]:
    """Aplica o catálogo ao banco. Idempotente.

    Recebe as classes de model para funcionar tanto com os models atuais
    (comando) quanto com os históricos (migração).

    Args:
        create_missing: Cria cursos do catálogo que não existem (instalação
            nova). A migração passa False: só ajusta o que já existe.
        prune: Remove termos dos cursos do catálogo que não estão nele. Apaga
            em cascata as vagas pré-buscadas desses termos (DailyJob).

    Returns:
        Contagens do que foi feito, para log/saída do comando.
    """
    stats = {"courses_created": 0, "courses_updated": 0, "terms_upserted": 0, "terms_pruned": 0}
    areas = {area.code: area for area in area_model.objects.all()}

    for entry in COURSES:
        course = course_model.objects.filter(code=entry["code"]).first()
        if course is None:
            if not create_missing:
                continue
            course = course_model.objects.create(
                code=entry["code"], name=entry["name"], order=entry["order"], **_COURSE_DEFAULTS
            )
            stats["courses_created"] += 1
        else:
            stats["courses_updated"] += 1

        course.area = areas.get(entry["area_code"], course.area)
        course.job_title_keywords = entry["job_title_keywords"]
        course.job_course_names = entry["job_course_names"]
        course.save(update_fields=["area", "job_title_keywords", "job_course_names"])

        catalog_terms = {row["term"] for row in entry["terms"]}
        if prune:
            stale = term_model.objects.filter(course=course).exclude(term__in=catalog_terms)
            stats["terms_pruned"] += stale.count()
            stale.delete()

        for row in entry["terms"]:
            fields = {k: v for k, v in row.items() if k != "term"}
            term_model.objects.update_or_create(
                course=course,
                term=row["term"],
                defaults={**fields, "is_default": True, "country_indeed": "Brazil"},
            )
            stats["terms_upserted"] += 1

    return stats
