import importlib

import pytest
from django.apps import apps as django_apps

from apps.jobs.models import Job
from apps.jobs.tests.factories import CompanyFactory, JobFactory

migracao = importlib.import_module("apps.jobs.migrations.0011_job_tipo_rotulos")


@pytest.mark.django_db
@pytest.mark.parametrize(
    "antigo, novo",
    [
        ("estagio", "Estágio"),
        ("clt", "CLT"),
        ("pj", "PJ"),
        ("temporario", "Temporário"),
    ],
)
def test_converte_slug_antigo_para_rotulo(antigo, novo):
    vaga = JobFactory(tipo=antigo)

    migracao.converter_tipos(django_apps, None)

    vaga.refresh_from_db()
    assert vaga.tipo == novo


@pytest.mark.django_db
@pytest.mark.parametrize("valor", ["Estágio", "CLT", "Contrato de aprendizagem", "Trainee"])
def test_valor_ja_rotulado_ou_livre_fica_igual(valor):
    vaga = JobFactory(tipo=valor)

    migracao.converter_tipos(django_apps, None)

    vaga.refresh_from_db()
    assert vaga.tipo == valor


@pytest.mark.django_db
def test_conversao_nao_mexe_em_outros_campos_nem_em_updated_at():
    vaga = JobFactory(tipo="estagio", titulo="Vaga X")
    antes = Job.objects.get(pk=vaga.pk).updated_at

    migracao.converter_tipos(django_apps, None)

    depois = Job.objects.get(pk=vaga.pk)
    assert depois.titulo == "Vaga X"
    assert depois.updated_at == antes


@pytest.mark.django_db
def test_reverso_devolve_os_slugs():
    empresa = CompanyFactory()
    vagas = {
        rotulo: JobFactory(company=empresa, tipo=rotulo)
        for rotulo in ["Estágio", "CLT", "PJ", "Temporário"]
    }

    migracao.desfazer_tipos(django_apps, None)

    obtidos = {rotulo: Job.objects.get(pk=v.pk).tipo for rotulo, v in vagas.items()}
    assert obtidos == {
        "Estágio": "estagio",
        "CLT": "clt",
        "PJ": "pj",
        "Temporário": "temporario",
    }
