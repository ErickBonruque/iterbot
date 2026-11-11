"""Converte o ``tipo`` das vagas de slug para rótulo.

O formulário da empresa gravava ``estagio``/``clt``/``pj``/``temporario`` e o
painel, o bot e o admin mostravam esse slug cru. Agora o valor gravado é o
próprio rótulo (``Estágio``, ``CLT``, ``PJ``, ``Temporário``). Só os quatro
slugs exatos são convertidos; qualquer outro texto (digitado no admin) fica
como está. Usa ``update()``, que não mexe em ``updated_at``.
"""

from django.db import migrations

SLUG_PARA_ROTULO = {
    "estagio": "Estágio",
    "clt": "CLT",
    "pj": "PJ",
    "temporario": "Temporário",
}


def converter_tipos(apps, schema_editor):
    Job = apps.get_model("jobs", "Job")
    for slug, rotulo in SLUG_PARA_ROTULO.items():
        Job.objects.filter(tipo=slug).update(tipo=rotulo)


def desfazer_tipos(apps, schema_editor):
    Job = apps.get_model("jobs", "Job")
    for slug, rotulo in SLUG_PARA_ROTULO.items():
        Job.objects.filter(tipo=rotulo).update(tipo=slug)


class Migration(migrations.Migration):
    dependencies = [
        ("jobs", "0010_dailyjob_source"),
    ]

    operations = [
        migrations.RunPython(converter_tipos, desfazer_tipos),
    ]
