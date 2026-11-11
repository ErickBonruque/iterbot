"""Fixtures compartilhadas pelos testes do portal da empresa."""

from django.contrib.auth.models import User

from apps.jobs.models import CompanyStatus
from apps.jobs.tests.factories import CompanyFactory


def usuario_com_empresa(username="dono", status=CompanyStatus.APPROVED, cnpj="11.222.333/0001-81"):
    """Cria um usuário com empresa vinculada (CNPJ único por chamada)."""
    user = User.objects.create_user(
        username=username, email=f"{username}@empresa.com", password="TestPass123!"
    )
    company = CompanyFactory(user=user, status=status, cnpj=cnpj, contato_nome="Mariana")
    return user, company
