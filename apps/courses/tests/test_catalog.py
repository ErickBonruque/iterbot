"""Catálogo de cursos/termos: fonte única para o seed e para a migração de produção."""

import pytest
from django.core.management import call_command

from apps.courses.catalog import COURSES, apply_catalog
from apps.courses.models import Area, Course, SearchTerm
from apps.jobs.relevance import REGIONAL, REMOTE, parse_terms


def _apply(**kwargs):
    return apply_catalog(Course, SearchTerm, Area, **kwargs)


# Áreas que a migração 0004 semeia. Testes com transaction=True (aqui e em outros
# apps) esvaziam as tabelas ao terminar — não dá para contar com o seed.
SEEDED_AREAS = {"ti": "Tecnologia da Informação", "agro-bio": "Ciências Agrárias e Biológicas"}


@pytest.fixture
def seeded_areas(db):
    for code, name in SEEDED_AREAS.items():
        Area.objects.get_or_create(code=code, defaults={"name": name})


@pytest.mark.django_db
@pytest.mark.usefixtures("seeded_areas")
class TestApplyCatalog:
    def test_creates_courses_with_area_and_keywords(self):
        Course.objects.all().delete()

        _apply(create_missing=True, prune=True)

        computacao = Course.objects.get(code="COENS")
        assert computacao.area.code == "ti"
        assert Course.objects.get(code="COAGR").area.code == "agro-bio"
        assert "desenvolv" in parse_terms(computacao.job_title_keywords)
        assert "ciencia da computacao" in parse_terms(computacao.job_course_names)

    def test_fixes_existing_course_without_area(self):
        # Produção: os cursos foram carregados depois da migração de áreas e
        # ficaram com area=None — "Vagas do meu curso" não achava nada da área.
        Course.objects.all().delete()
        Course.objects.create(code="COBIO", name="Ciências Biológicas", area=None)

        _apply(create_missing=False, prune=True)

        assert Course.objects.get(code="COBIO").area.code == "agro-bio"

    def test_replaces_legacy_terms_when_pruning(self):
        Course.objects.all().delete()
        course = Course.objects.create(code="COAGR", name="Agronomia")
        SearchTerm.objects.create(course=course, term="estágio fitossanidade", location="Brasil")

        stats = _apply(create_missing=False, prune=True)

        terms = set(course.search_terms.values_list("term", flat=True))
        assert "estágio fitossanidade" not in terms
        assert terms == {row["term"] for row in COURSES[1]["terms"]}
        assert stats["terms_pruned"] == 1

    def test_without_prune_keeps_admin_terms(self):
        Course.objects.all().delete()
        course = Course.objects.create(code="COAGR", name="Agronomia")
        SearchTerm.objects.create(course=course, term="termo do admin")

        _apply(create_missing=False, prune=False)

        assert course.search_terms.filter(term="termo do admin").exists()

    def test_does_not_create_courses_unless_asked(self):
        Course.objects.all().delete()
        _apply(create_missing=False, prune=True)
        assert not Course.objects.exists()

    def test_is_idempotent(self):
        Course.objects.all().delete()
        _apply(create_missing=True, prune=True)
        _apply(create_missing=True, prune=True)
        assert Course.objects.count() == len(COURSES)
        assert SearchTerm.objects.count() == sum(len(c["terms"]) for c in COURSES)

    def test_seed_command_uses_catalog(self):
        Course.objects.all().delete()
        call_command("seed_courses")
        assert Course.objects.count() == len(COURSES)
        for entry in COURSES:
            course = Course.objects.get(code=entry["code"])
            assert course.job_title_keywords == entry["job_title_keywords"]
            assert set(course.search_terms.values_list("term", flat=True)) == {
                row["term"] for row in entry["terms"]
            }


class TestCatalogContent:
    """Guarda as lições das buscas reais contra regressão."""

    def test_no_term_uses_portuguese_country_name(self):
        # LinkedIn não entende "Brasil" e devolve vagas dos EUA
        locations = {row["location"] for c in COURSES for row in c["terms"]}
        assert not any("Brasil" in loc for loc in locations)

    def test_every_term_has_a_relevance_scope_and_label(self):
        for course in COURSES:
            for row in course["terms"]:
                assert row["scope"] in (REGIONAL, REMOTE), row["term"]
                assert row["label"], row["term"]

    def test_glassdoor_is_not_used_with_long_location(self):
        # Glassdoor responde "location not found" para "Santa Helena, Paraná, Brazil"
        for course in COURSES:
            for row in course["terms"]:
                if "glassdoor" in row["site_name"]:
                    assert row["location"].count(",") == 1, row["term"]


@pytest.mark.django_db(transaction=True)
class TestCatalogMigration:
    """Reproduz a produção: cursos sem área e os 35 termos antigos com "Brasil"."""

    def test_migration_fixes_production_state(self):
        from django.db import connection
        from django.db.migrations.executor import MigrationExecutor

        before = [("courses", "0005_searchterm_scope_label_course_keywords")]
        after = [("courses", "0006_apply_course_catalog")]

        executor = MigrationExecutor(connection)
        executor.migrate(before)
        old_apps = executor.loader.project_state(before).apps
        OldCourse = old_apps.get_model("courses", "Course")  # noqa: N806
        OldTerm = old_apps.get_model("courses", "SearchTerm")  # noqa: N806
        OldArea = old_apps.get_model("courses", "Area")  # noqa: N806
        for code, name in SEEDED_AREAS.items():
            OldArea.objects.get_or_create(code=code, defaults={"name": name})
        OldCourse.objects.all().delete()
        course = OldCourse.objects.create(code="COENS", name="Ciência da Computação", area=None)
        OldTerm.objects.create(course=course, term="estágio desenvolvedor", location="Brasil")

        executor = MigrationExecutor(connection)
        executor.loader.build_graph()
        executor.migrate(after)

        migrated = Course.objects.get(code="COENS")
        assert migrated.area.code == "ti"
        terms = SearchTerm.objects.filter(course=migrated)
        assert not terms.filter(location="Brasil").exists()
        assert terms.filter(scope="regional").exists()
