import re

import pytest
from django.contrib import messages
from django.contrib.auth.models import AnonymousUser
from django.contrib.messages.storage.fallback import FallbackStorage
from django.template.loader import render_to_string
from django.test import RequestFactory
from django.urls import resolve

LAYOUTS = ["layouts/entrada.html", "layouts/portal.html", "layouts/simples.html"]


def _request(path="/empresas/perfil/"):
    request = RequestFactory().get(path)
    request.user = AnonymousUser()
    request.session = {}
    request._messages = FallbackStorage(request)
    return request


@pytest.mark.parametrize("template", ["base.html", *LAYOUTS])
def test_base_usa_portal_css_e_mascote(template):
    html = render_to_string(template, request=_request())

    assert "css/portal.css" in html
    assert "img/mascote.png" in html
    assert "logo-icon.png" not in html
    assert "<style" not in html


@pytest.mark.parametrize("template", LAYOUTS)
def test_mensagens_renderizadas_uma_vez(template):
    request = _request()
    messages.success(request, "Vaga salva com sucesso")

    html = render_to_string(template, request=request)

    assert html.count("Vaga salva com sucesso") == 1


def test_mensagem_error_vira_alert_danger():
    request = _request()
    messages.error(request, "Não foi possível salvar")

    html = render_to_string("layouts/portal.html", request=request)

    assert "alert-danger" in html
    assert "alert-error" not in html


@pytest.mark.parametrize(
    "nivel, classe",
    [
        (messages.SUCCESS, "alert-success"),
        (messages.WARNING, "alert-warning"),
        (messages.INFO, "alert-info"),
    ],
)
def test_mensagem_mantem_classe_dos_outros_niveis(nivel, classe):
    request = _request()
    messages.add_message(request, nivel, "Aviso qualquer")

    html = render_to_string("layouts/simples.html", request=request)

    assert classe in html


@pytest.mark.parametrize(
    "variante, esperado, ausente",
    [
        ("claro", "img/logo-utfpr.png", "logo-utfpr-branco"),
        ("escuro", "img/logo-utfpr-branco.png", "logo-utfpr.png"),
    ],
)
def test_logo_utfpr_escolhe_arquivo_pelo_fundo(variante, esperado, ausente):
    html = render_to_string("includes/logo_utfpr.html", {"variante": variante, "classe": "logo-x"})

    assert esperado in html
    assert ausente not in html
    assert 'class="img-utfpr logo-x"' in html
    assert "UTFPR" in html


@pytest.mark.parametrize(
    "template, arquivo",
    [
        ("layouts/entrada.html", "img/logo-utfpr.png"),
        ("layouts/portal.html", "img/logo-utfpr-branco.png"),
        ("layouts/simples.html", "img/logo-utfpr-branco.png"),
    ],
)
def test_cada_layout_mostra_o_logo_da_utfpr_uma_vez(template, arquivo):
    html = render_to_string(template, request=_request())

    assert html.count("logo-utfpr") == 1
    assert arquivo in html


@pytest.mark.parametrize("caminho", ["/empresas/candidaturas/", "/empresas/perfil/"])
def test_portal_marca_so_o_item_ativo_da_url(caminho):
    request = _request(caminho)
    request.resolver_match = resolve(caminho)

    html = render_to_string("layouts/portal.html", request=request)

    ativos = re.findall(r"<a [^>]*\bativo\b[^>]*>", html)
    assert len(ativos) == 1
    assert caminho in ativos[0]
