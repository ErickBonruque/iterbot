"""Template tags do portal da empresa.

Carregar com ``{% load portal %}``: WhatsApp legível e com link, selos de status
(vaga e candidatura) e o contador de candidaturas novas do menu.
"""

from django import template

from apps.jobs.models import ApplicationStatus, JobApplication, JobStatus

register = template.Library()

_SUFIXO_WHATSAPP = "@c.us"
_CLASSE_NEUTRA = "st-neutro"

# Chaves são os valores (str) dos enums, para o lookup não depender do hash do Enum.
_SELOS_VAGA = {
    JobStatus.DRAFT.value: ("Rascunho", _CLASSE_NEUTRA),
    JobStatus.PENDING.value: ("Em análise", "st-analise"),
    JobStatus.APPROVED.value: ("Publicada", "st-ok"),
    JobStatus.REJECTED.value: ("Recusada", "st-recusada"),
    JobStatus.EXPIRED.value: ("Expirada", _CLASSE_NEUTRA),
    JobStatus.REMOVED.value: ("Removida", _CLASSE_NEUTRA),
}

_SELOS_CANDIDATURA = {
    ApplicationStatus.PENDING.value: ("Nova", "st-nova"),
    ApplicationStatus.VISTA.value: ("Vista", _CLASSE_NEUTRA),
    ApplicationStatus.CONTATADO.value: ("Contatado", "st-ok"),
    ApplicationStatus.REJEITADA.value: ("Recusada", "st-recusada"),
}


def _telefone_brasileiro(phone_number):
    """Dígitos de um telefone +55 válido (12 ou 13 dígitos) ou ``None``.

    Aceita o id do WAHA (``5545999990000@c.us``) ou só os dígitos. Qualquer outra
    coisa (``123@lid``, grupo, vazio, número de outro país) não é telefone: devolve
    ``None`` para o template não inventar formato nem link quebrado.
    """
    if not isinstance(phone_number, str):
        return None
    digitos = phone_number.removesuffix(_SUFIXO_WHATSAPP)
    if not (digitos.isascii() and digitos.isdigit()):
        return None
    if not digitos.startswith("55") or len(digitos) not in (12, 13):
        return None
    return digitos


@register.filter
def whatsapp_display(phone_number):
    """``5545999990000@c.us`` → ``(45) 99999-0000``; ``""`` quando não é telefone."""
    digitos = _telefone_brasileiro(phone_number)
    if digitos is None:
        return ""
    ddd, numero = digitos[2:4], digitos[4:]
    corte = len(numero) - 4
    return f"({ddd}) {numero[:corte]}-{numero[corte:]}"


@register.filter
def whatsapp_link(phone_number):
    """Link ``https://wa.me/<dígitos>``; ``""`` quando não é telefone."""
    digitos = _telefone_brasileiro(phone_number)
    return f"https://wa.me/{digitos}" if digitos else ""


def _selo(tabela, status):
    rotulo, classe = tabela.get(str(status), (str(status), _CLASSE_NEUTRA))
    return {"rotulo": rotulo, "classe": classe}


@register.simple_tag
def selo_vaga(status):
    """Rótulo e classe CSS do selo de uma vaga (``{% selo_vaga job.status as selo %}``)."""
    return _selo(_SELOS_VAGA, status)


@register.simple_tag
def selo_candidatura(status):
    """Rótulo e classe CSS do selo de uma candidatura."""
    return _selo(_SELOS_CANDIDATURA, status)


@register.simple_tag(takes_context=True)
def candidaturas_novas(context):
    """Candidaturas ``pending`` das vagas da empresa do usuário logado (0 sem empresa).

    Consulta direta e sem efeito colateral: roda em toda página do portal, então
    não usa ``CompaniesService.get_user_company_or_none`` (que pode gravar).
    """
    user = getattr(context.get("request"), "user", None)
    if user is None or not user.is_authenticated:
        return 0
    return JobApplication.objects.filter(
        job__company__user=user, status=ApplicationStatus.PENDING
    ).count()
