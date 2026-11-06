"""Liga a Adzuna nos termos do catálogo já existentes em produção.

Só atualiza `site_name` dos termos que estão no catálogo (as palavras-chave e
demais campos, possivelmente editados no admin, ficam como estão). Instalação
nova recebe os termos já com a Adzuna pelo `seed_courses`.
"""

from django.db import migrations, models


def enable_adzuna(apps, schema_editor):
    from apps.courses.catalog import COURSES

    SearchTerm = apps.get_model("courses", "SearchTerm")
    for course in COURSES:
        for row in course["terms"]:
            SearchTerm.objects.filter(course__code=course["code"], term=row["term"]).update(
                site_name=row["site_name"]
            )


def disable_adzuna(apps, schema_editor):
    SearchTerm = apps.get_model("courses", "SearchTerm")
    for term in SearchTerm.objects.filter(site_name__contains="adzuna"):
        sites = [s for s in term.site_name.split(",") if s.strip() and s.strip() != "adzuna"]
        term.site_name = ",".join(sites) or "indeed"
        term.save(update_fields=["site_name"])


class Migration(migrations.Migration):
    dependencies = [
        ("courses", "0006_apply_course_catalog"),
    ]

    operations = [
        migrations.AlterField(
            model_name="searchterm",
            name="site_name",
            field=models.CharField(
                default="linkedin,indeed,glassdoor",
                help_text=(
                    "Sites de busca separados por vírgula: linkedin, indeed, glassdoor, adzuna. "
                    "LinkedIn ignora cidade e 'apenas remotas'; Indeed e Adzuna respeitam a "
                    "cidade (a Adzuna não tem filtro de remoto: usa a palavra 'remoto')."
                ),
                max_length=100,
            ),
        ),
        migrations.RunPython(enable_adzuna, disable_adzuna),
    ]
