"""Aplica o catálogo de cursos/termos (apps.courses.catalog) a cursos existentes.

Em produção:
- os 3 cursos estavam sem área (foram carregados depois da 0004_seed_areas);
- os 35 termos antigos usavam "Brasil" (LinkedIn devolvia vagas dos EUA) e
  termos específicos que voltavam vazios na região.

Só mexe em cursos que já existem (instalação nova recebe os cursos pelo
`seed_courses`). Remove os termos fora do catálogo — e, em cascata, as vagas
pré-buscadas deles; a próxima execução de `fetch_daily_jobs` repõe.
"""

from django.db import migrations


def apply(apps, schema_editor):
    from apps.courses.catalog import apply_catalog

    apply_catalog(
        apps.get_model("courses", "Course"),
        apps.get_model("courses", "SearchTerm"),
        apps.get_model("courses", "Area"),
        create_missing=False,
        prune=True,
    )


class Migration(migrations.Migration):
    dependencies = [
        ("courses", "0005_searchterm_scope_label_course_keywords"),
        ("jobs", "0009_jobapplication_message_and_more"),  # DailyJob (cascade)
        ("bot", "0008_alter_botmessage_key"),  # ConversationState.selected_term (set null)
    ]

    operations = [migrations.RunPython(apply, migrations.RunPython.noop)]
