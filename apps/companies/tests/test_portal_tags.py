import pytest
from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.template import Context, Template
from django.template.loader import render_to_string
from django.test import RequestFactory

from apps.companies.templatetags.portal import (
    link_http,
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


class _FormExemplo(forms.Form):
    titulo = forms.CharField(
        label="Título", widget=forms.TextInput(attrs={"class": "form-control"})
    )


def _widget(form):
    template = Template("{% load portal %}{% campo_widget form.titulo %}")
    return template.render(Context({"form": form}))


def test_campo_widget_sem_erro_nao_marca_is_invalid():
    form = _FormExemplo(data={"titulo": "ok"})
    form.is_valid()

    html = _widget(form)

    assert 'class="form-control"' in html
    assert "is-invalid" not in html


def test_campo_widget_com_erro_marca_is_invalid_e_mantem_a_classe():
    form = _FormExemplo(data={"titulo": ""})
    form.is_valid()

    html = _widget(form)

    assert 'class="form-control is-invalid"' in html


def test_campo_widget_em_formulario_nao_enviado_nao_marca_erro():
    assert "is-invalid" not in _widget(_FormExemplo())


def test_include_campo_mostra_rotulo_obrigatorio_e_mensagem_de_erro():
    form = _FormExemplo(data={"titulo": ""})
    form.is_valid()

    html = render_to_string("includes/campo.html", {"campo": form["titulo"]})

    assert "Título *" in html
    assert "invalid-feedback" in html
    assert "is-invalid" in html


@pytest.mark.parametrize(
    "url, esperado",
    [
        ("https://linkedin.com/in/fulano", "https://linkedin.com/in/fulano"),
        ("http://exemplo.com/cv.pdf", "http://exemplo.com/cv.pdf"),
        ("  https://exemplo.com  ", "https://exemplo.com"),
        ("javascript:alert(1)", ""),
        ("JavaScript:alert(1)", ""),
        ("java\tscript:alert(1)", ""),
        (" javascript:alert(1)", ""),
        ("data:text/html,<script>alert(1)</script>", ""),
        ("//exemplo.com/sem-esquema", ""),
        ("", ""),
        (None, ""),
    ],
)
def test_link_http_so_deixa_passar_http_e_https(url, esperado):
    assert link_http(url) == esperado


class _FormAllauth(forms.Form):
    """Campo sem classe nenhuma, como os do allauth."""

    email = forms.EmailField(label="E-mail")
    escolha = forms.ChoiceField(
        choices=[("a", "A")], widget=forms.Select(attrs={"class": "form-select"})
    )


def _widget_com_classe(campo, classe):
    template = Template("{% load portal %}{% campo_widget campo classe %}")
    return template.render(Context({"campo": campo, "classe": classe}))


def test_campo_widget_soma_a_classe_pedida_ao_campo_sem_classe():
    form = _FormAllauth(data={"email": "a@b.com", "escolha": "a"})
    form.is_valid()

    assert 'class="form-control"' in _widget_com_classe(form["email"], "form-control")


def test_campo_widget_nao_repete_classe_que_o_widget_ja_tem():
    form = _FormAllauth(data={"email": "a@b.com", "escolha": "a"})
    form.is_valid()

    html = _widget_com_classe(form["escolha"], "form-select")

    assert html.count("form-select") == 1


def test_campo_widget_classe_pedida_e_is_invalid_convivem():
    form = _FormAllauth(data={"email": "", "escolha": "a"})
    form.is_valid()

    assert 'class="form-control is-invalid"' in _widget_com_classe(form["email"], "form-control")


def test_include_campo_aceita_rotulo_proprio_e_sem_asterisco():
    form = _FormAllauth()

    html = render_to_string(
        "includes/campo.html",
        {
            "campo": form["email"],
            "rotulo": "Seu e-mail",
            "sem_asterisco": True,
            "classe": "form-control",
        },
    )

    assert ">Seu e-mail</label>" in html
    assert "*" not in html
    assert 'class="form-control"' in html


def test_include_campo_mostra_ajuda_quando_recebe():
    form = _FormAllauth(data={})

    html = render_to_string(
        "includes/campo.html", {"campo": form["email"], "ajuda": "Use o e-mail da empresa."}
    )

    assert "Use o e-mail da empresa." in html
