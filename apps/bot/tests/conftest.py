"""Fixtures compartilhadas dos testes do bot."""

import pytest
from django.utils import timezone

from apps.users.models import UserProfile


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "no_consent_default: perfis nascem SEM aceite de privacidade (testa o portão LGPD)",
    )


@pytest.fixture(autouse=True)
def _consented_profiles_by_default(request, monkeypatch):
    """Perfis criados nos testes do bot já nascem com o aceite de privacidade.

    Quase todos os testes do bot exercitam fluxos de quem já passou do primeiro
    contato (aceitou o texto de privacidade). O portão em si é testado em
    `test_privacy_consent.py`, marcado com `no_consent_default`, onde o perfil
    nasce sem aceite como em produção.
    """
    if request.node.get_closest_marker("no_consent_default"):
        return
    field = UserProfile._meta.get_field("privacy_consent_at")
    # `_get_default` é cached_property; atributo de instância tem precedência.
    monkeypatch.setattr(field, "_get_default", timezone.now, raising=False)
