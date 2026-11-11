"""Filtro de relevância das vagas online — casos tirados de buscas reais (nov/2026)."""

import pytest

from apps.jobs.relevance import (
    REGIONAL,
    REMOTE,
    classify,
    dedupe,
    is_in_brazil,
    is_in_region,
    parse_terms,
)

CC = parse_terms("desenvolvedor\nprogramação\nsoftware\ndados\nTI\nsuporte técnico")
AGRO = parse_terms("agronomia, agrícola, agronegócio")
BIO = parse_terms("biologia\nambiental\nlaboratório")
CC_COURSE = parse_terms("Ciência da Computação\nSistemas de Informação")


def job(title, location="Cascavel, PR, Brazil", **extra):
    return {"title": title, "location": location, "company": "Empresa", **extra}


def verdict(record, keywords, scope, course_names=(), board_remote=False):
    return classify(
        record,
        title_keywords=keywords,
        course_names=list(course_names),
        scope=scope,
        board_remote=board_remote,
    )


class TestParseTerms:
    def test_accepts_lines_and_commas_and_normalizes_accents(self):
        assert parse_terms("Agronomia, agrícola\n  Ciência da Computação \n\n") == [
            "agronomia",
            "agricola",
            "ciencia da computacao",
        ]


class TestRegional:
    def test_area_internship_in_region_is_kept(self):
        record = job("Estágio - Gestão Ambiental", "Medianeira, Paraná, Brazil")
        assert verdict(record, BIO, REGIONAL) == "ok"

    def test_generic_internship_is_out_of_area(self):
        record = job("Estágio - Sede Administrativa da Sicredi Vanguarda", "Medianeira, PR")
        assert verdict(record, CC, REGIONAL) == "fora_area"

    def test_course_named_in_description_counts_as_area(self):
        # "pedem curso de computação": o título é genérico, a descrição pede o curso
        record = job(
            "Estágio em Inteligência Comercial",
            "Toledo, PR, Brazil",
            description="Requisitos: cursando Ciência da Computação ou áreas afins.",
        )
        assert verdict(record, CC, REGIONAL, course_names=CC_COURSE) == "ok"

    def test_non_internship_is_rejected(self):
        record = job("Analista de Crédito PF e Agro - Palotina", "Palotina, Brazil")
        assert verdict(record, AGRO, REGIONAL) == "nao_estagio"

    @pytest.mark.parametrize(
        "title",
        [
            "JOVEM APRENDIZ NA ÁREA DE PRODUÇÃO",
            "AUXILIAR ADM APRENDIZ - 0069",
            "Desenvolvedor Sênior",
            "Gerente de Plantão Trainee",
        ],
    )
    def test_excluded_titles(self, title):
        assert verdict(job(title), CC, REGIONAL) == "excluido"

    def test_outside_region_is_rejected(self):
        record = job("Estagiário de Agronomia - Sarandi/PR", "Sarandi, Paraná, Brazil")
        assert verdict(record, AGRO, REGIONAL) == "fora_regiao"

    def test_unknown_location_is_rejected_for_regional(self):
        assert verdict(job("Estágio TI", None), CC, REGIONAL) == "fora_regiao"


class TestRemote:
    def test_remote_junior_in_area_is_kept(self):
        record = job("Desenvolvedor Python Junior - Trabalho Remoto", "Rio de Janeiro, Brazil")
        assert verdict(record, CC, REMOTE) == "ok"

    def test_junior_is_not_an_internship_for_regional(self):
        record = job("Desenvolvedor Python Junior", "Cascavel, PR, Brazil")
        assert verdict(record, CC, REGIONAL) == "nao_estagio"

    def test_board_remote_filter_is_trusted(self):
        # O Indeed aplica o filtro de remoto; o título nem sempre diz "remoto"
        record = job("Estágio em Desenvolvimento de Software", "São Paulo, SP, Brazil")
        assert verdict(record, CC, REMOTE, board_remote=True) == "ok"

    def test_without_remote_signal_is_rejected(self):
        # LinkedIn ignora is_remote: sem sinal no texto, é presencial
        record = job("Estágio em Desenvolvimento de Software", "São Paulo, SP, Brazil")
        assert verdict(record, CC, REMOTE) == "nao_remoto"

    @pytest.mark.parametrize(
        "description",
        [
            # Vagas de suporte de TI presenciais que a Adzuna devolveu como "remoto"
            "Auxiliar no suporte help desk, acesso remoto. Levantar melhorias.",
            "Atendimento de chamados aos usuários no formato local e remoto.",
            "Ferramentas de acesso remoto; tipo de vaga: estágio.",
            "Atendimento ao usuário remoto e presencial; apoio nas reuniões.",
            "Suporte técnico aos usuários, presenciais e remotos.",
        ],
    )
    def test_remote_support_jargon_is_not_remote_work(self, description):
        record = job("Estágio em TI", "Belo Horizonte, Minas Gerais", description=description)
        assert verdict(record, CC, REMOTE) == "nao_remoto"

    def test_remote_support_role_in_title_is_kept(self):
        record = job("Estágio Suporte Técnico - Remoto", "Brasil")
        assert verdict(record, CC, REMOTE) == "ok"

    def test_remote_work_in_description_is_kept(self):
        record = job(
            "Estágio em Análise de Dados",
            "São Paulo, Estado de São Paulo",
            description="Vaga para estágio. Você poderá trabalhar remoto de qualquer lugar.",
        )
        assert verdict(record, CC, REMOTE) == "ok"

    def test_hybrid_is_not_remote_even_with_board_flag(self):
        record = job("Pessoa Desenvolvedora Fullstack Jr (Híbrido - Manaus)", "Manaus, AM, Brazil")
        assert verdict(record, CC, REMOTE, board_remote=True) == "nao_remoto"

    def test_experienced_remote_role_is_rejected(self):
        record = job("Analista de Dados - Remoto", "Brazil")
        assert verdict(record, CC, REMOTE) == "nivel"

    def test_foreign_location_is_rejected(self):
        record = job("Software Engineer Intern (Remote)", "Seattle, WA")
        assert verdict(record, CC, REMOTE) == "fora_brasil"


class TestLocation:
    @pytest.mark.parametrize(
        "location",
        [
            "Cascavel, PR, Brazil",
            "Greater São Paulo Area",
            "Remoto, Brazil",
            "Paraná, Brazil",
            "",
            # Formato da Adzuna: estado por extenso, sem país.
            "Castanhal, Pará",
            "Toledo, Paraná",
        ],
    )
    def test_brazilian_or_unknown(self, location):
        assert is_in_brazil(location)

    @pytest.mark.parametrize(
        "location",
        ["Los Angeles, CA", "Cebu, Philippines", "Strongsville, OH", "Pittsburgh, PA"],
    )
    def test_foreign(self, location):
        assert not is_in_brazil(location)

    def test_region_matches_oeste_parana_cities(self):
        assert is_in_region("Foz do Iguaçu, PR, Brazil")
        assert is_in_region("Marechal Cândido Rondon, Paraná, Brazil")
        assert not is_in_region("Curitiba, PR, Brazil")
        # Toledo da Espanha não é Toledo-PR
        assert not is_in_region("Toledo, Castilla-La Mancha, Spain")


class TestDedupe:
    def test_same_job_on_two_boards_keeps_the_one_with_description(self):
        glassdoor = job("Estágio - Gestão Ambiental", "Medianeira, Paraná, Brazil", company="Lar")
        indeed = job(
            "Estágio - Gestão Ambiental",
            "Medianeira, PR, Brazil",
            company="Senior Sistemas",
            description="Cursando Ciências Biológicas",
        )
        assert dedupe([glassdoor, indeed]) == [indeed]

    def test_same_title_and_company_in_many_cities_collapses(self):
        records = [
            job("Desenvolvedor Python Junior - Trabalho Remoto", city, company="BairesDev")
            for city in ("São Paulo, Brazil", "Natal, Brazil", "Salvador, Brazil")
        ]
        assert len(dedupe(records)) == 1

    def test_caps_jobs_per_company(self):
        records = [job(f"Desenvolvedor Junior {stack}", company="BairesDev") for stack in "ABCD"]
        records.append(job("Estágio TI", company="Outra"))
        kept = dedupe(records, max_per_company=2)
        assert [r["company"] for r in kept] == ["BairesDev", "BairesDev", "Outra"]


class TestCourseWithoutKeywords:
    def test_area_is_not_enforced_when_course_has_no_keywords(self):
        # Curso novo cadastrado no admin sem palavras-chave não pode ficar sem
        # nenhuma vaga — filtra local/nível, mas não a área
        record = job("Estágio - Agência", "Cascavel, PR, Brazil")
        assert verdict(record, [], REGIONAL) == "ok"
