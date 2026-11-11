import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.template import Context, Template
from django.test import RequestFactory

from apps.companies.templatetags.portal import (
    selo_candidatura,
    selo_vaga,
    whatsapp_display,
    whatsapp_link,
)
from apps.jobs.models import ApplicationStatus
from apps.jobs.tests.factories import CompanyFactory, JobApplicationFactory, JobFactory
from apps.users.tests.factories import UserProfileFactory

User = get_user_model()


@pytest.mark.parametrize(
    "raw, shown, link",
    [
        ("5545999990000@c.us", "(45) 99999-0000", "https://wa.me/5545999990000"),
        ("554599990000@c.us", "(45) 9999-0000", "https://wa.me/554599990000"),
        ("5545999990000", "(45) 99999-0000", "https://wa.me/5545999990000"),
        ("123456789012345@lid", "", ""),
        ("", "", ""),
        (None, "", ""),
        ("14155550000@c.us", "", ""),  # não é +55: não inventa formato
        ("5545999990000@g.us", "", ""),  # grupo não é telefone
        ("55459999@c.us", "", ""),  # curto demais
        ("554599999000012@c.us", "", ""),  # longo demais
    ],
)
def test_whatsapp(raw, shown, link):
    assert whatsapp_display(raw) == shown
    assert whatsapp_link(raw) == link


def test_selo_vaga():
    assert selo_vaga("pending") == {"rotulo": "Em análise", "classe": "st-analise"}
    assert selo_vaga("approved") == {"rotulo": "Publicada", "classe": "st-ok"}
    assert selo_vaga("rejected") == {"rotulo": "Recusada", "classe": "st-recusada"}
    assert selo_vaga("expired")["rotulo"] == "Expirada"
    assert selo_vaga("draft") == {"rotulo": "Rascunho", "classe": "st-neutro"}
    assert selo_vaga("removed") == {"rotulo": "Removida", "classe": "st-neutro"}


def test_selo_candidatura():
    assert selo_candidatura("pending") == {"rotulo": "Nova", "classe": "st-nova"}
    assert selo_candidatura("contatado")["classe"] == "st-ok"
    assert selo_candidatura("vista") == {"rotulo": "Vista", "classe": "st-neutro"}
    assert selo_candidatura("rejeitada") == {"rotulo": "Recusada", "classe": "st-recusada"}


@pytest.mark.parametrize("selo", [selo_vaga, selo_candidatura])
def test_selo_desconhecido_mostra_o_rotulo_cru_e_fica_neutro(selo):
    assert selo("algo_novo") == {"rotulo": "algo_novo", "classe": "st-neutro"}


def _contar(user):
    request = RequestFactory().get("/")
    request.user = user
    template = Template("{% load portal %}{% candidaturas_novas as n %}{{ n }}")
    return int(template.render(Context({"request": request})))


@pytest.mark.django_db
def test_candidaturas_novas_conta_so_pending_da_empresa():
    dono = User.objects.create_user(username="dono", email="dono@empresa.com", password="x")
    outro = User.objects.create_user(username="outro", email="outro@empresa.com", password="x")
    minha = CompanyFactory(user=dono)
    alheia = CompanyFactory(user=outro, cnpj="22.333.444/0001-81")
    vaga_minha = JobFactory(company=minha)
    vaga_alheia = JobFactory(company=alheia)

    JobApplicationFactory(job=vaga_minha, user=UserProfileFactory())
    JobApplicationFactory(job=vaga_minha, user=UserProfileFactory())
    JobApplicationFactory(job=vaga_minha, user=UserProfileFactory(), status=ApplicationStatus.VISTA)
    JobApplicationFactory(job=vaga_alheia, user=UserProfileFactory())

    assert _contar(dono) == 2
    assert _contar(outro) == 1


@pytest.mark.django_db
def test_candidaturas_novas_e_zero_sem_empresa_ou_sem_login():
    sem_empresa = User.objects.create_user(username="s", email="s@x.com", password="x")

    assert _contar(sem_empresa) == 0
    assert _contar(AnonymousUser()) == 0
