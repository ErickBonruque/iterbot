from django.db import migrations

# Áreas iniciais (name, code, icon, order)
INITIAL_AREAS = [
    ("Tecnologia da Informação", "ti", "💻", 1),
    ("Engenharias", "eng", "⚙️", 2),
    ("Gestão e Negócios", "gestao", "📊", 3),
    ("Saúde", "saude", "🩺", 4),
    ("Ciências Agrárias e Biológicas", "agro-bio", "🌱", 5),
    ("Outras", "outras", "📚", 99),
]

# Mapeamento curso -> área. Chaves comparadas (case-insensitive) contra o nome
# e o código do curso. Cursos sem correspondência ficam com area=null.
COURSE_NAME_TO_AREA = {
    "ciência da computação": "Tecnologia da Informação",
    "ciencia da computacao": "Tecnologia da Informação",
    "engenharia de software": "Tecnologia da Informação",
    "sistemas de informação": "Tecnologia da Informação",
    "análise e desenvolvimento de sistemas": "Tecnologia da Informação",
    "engenharia": "Engenharias",
    "agronomia": "Ciências Agrárias e Biológicas",
    "ciências biológicas": "Ciências Agrárias e Biológicas",
    "ciencias biologicas": "Ciências Agrárias e Biológicas",
    "administração": "Gestão e Negócios",
    "administracao": "Gestão e Negócios",
}


def _resolve_area_name(course):
    name = (course.name or "").strip().lower()
    if name in COURSE_NAME_TO_AREA:
        return COURSE_NAME_TO_AREA[name]
    # match parcial por prefixo (ex.: "Engenharia Mecânica" -> Engenharias)
    for key, area_name in COURSE_NAME_TO_AREA.items():
        if name.startswith(key):
            return area_name
    return None


def seed_areas(apps, schema_editor):
    Area = apps.get_model("courses", "Area")
    Course = apps.get_model("courses", "Course")

    areas_by_name = {}
    for name, code, icon, order in INITIAL_AREAS:
        area, _ = Area.objects.get_or_create(
            name=name,
            defaults={"code": code, "icon": icon, "order": order, "is_active": True},
        )
        areas_by_name[name] = area

    for course in Course.objects.all():
        if course.area_id is not None:
            continue
        area_name = _resolve_area_name(course)
        if area_name:
            course.area = areas_by_name[area_name]
            course.save(update_fields=["area"])


def unseed_areas(apps, schema_editor):
    Area = apps.get_model("courses", "Area")
    Course = apps.get_model("courses", "Course")
    Course.objects.filter(area__isnull=False).update(area=None)
    Area.objects.filter(name__in=[a[0] for a in INITIAL_AREAS]).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("courses", "0003_area_course_area"),
    ]

    operations = [
        migrations.RunPython(seed_areas, unseed_areas),
    ]
