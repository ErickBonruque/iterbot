import pytest
from django.db import IntegrityError

from apps.courses.models import Area, Course


@pytest.mark.django_db
class TestAreaModel:
    def test_create_area_with_defaults(self):
        area = Area.objects.create(name="Área de Teste Defaults")
        assert area.is_active is True
        assert area.order == 0
        assert area.code is None
        assert area.icon == ""
        assert str(area) == "Área de Teste Defaults"

    def test_area_name_is_unique(self):
        Area.objects.create(name="Área de Teste Única")
        with pytest.raises(IntegrityError):
            Area.objects.create(name="Área de Teste Única")

    def test_area_ordering(self):
        Area.objects.all().delete()
        Area.objects.create(name="Beta", order=2)
        Area.objects.create(name="Alfa", order=1)
        Area.objects.create(name="Gama", order=1)
        names = list(Area.objects.values_list("name", flat=True))
        # ordena por order, depois name
        assert names == ["Alfa", "Gama", "Beta"]


@pytest.mark.django_db
class TestCourseArea:
    def test_course_without_area_is_null(self):
        course = Course.objects.create(name="Curso Sem Área")
        assert course.area is None

    def test_associate_course_to_area(self):
        area = Area.objects.create(name="Área de Teste Associação")
        course = Course.objects.create(name="Ciência da Computação", area=area)
        assert course.area == area
        assert list(area.courses.all()) == [course]

    def test_deleting_area_sets_course_area_null(self):
        area = Area.objects.create(name="Área de Teste Delete")
        course = Course.objects.create(name="Enfermagem", area=area)
        area.delete()
        course.refresh_from_db()
        assert course.area is None


@pytest.mark.django_db
class TestSeedAreasDataMigration:
    """Verifica o efeito da data migration 0004_seed_areas já aplicada."""

    def test_initial_areas_exist(self):
        expected = {
            "Tecnologia da Informação",
            "Engenharias",
            "Gestão e Negócios",
            "Saúde",
            "Ciências Agrárias e Biológicas",
            "Outras",
        }
        existing = set(Area.objects.values_list("name", flat=True))
        assert expected.issubset(existing)
