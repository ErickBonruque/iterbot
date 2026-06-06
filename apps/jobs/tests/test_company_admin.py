"""
Testes de unit para as admin actions do CompanyAdmin (PORTAL-02).

Usa RequestFactory + FallbackStorage para testar as actions diretamente
sem subir servidor HTTP — padrão estabelecido em apps/courses/tests/test_admin.py.
"""

import pytest
from django.contrib.messages import constants as message_constants
from django.contrib.messages.storage.fallback import FallbackStorage

from apps.jobs.admin.company import CompanyAdmin
from apps.jobs.models.company import Company, CompanyStatus
from apps.jobs.tests.factories import CompanyFactory


@pytest.fixture
def admin_user(db):
    from django.contrib.auth import get_user_model

    user_model = get_user_model()
    return user_model.objects.create_superuser(
        username="admin", password="pass", email="admin@test.com"
    )


@pytest.mark.django_db
class TestCompanyAdminApproveAction:
    """approve_companies: muda status de PENDING para APPROVED."""

    def test_approve_changes_status_to_approved(self, rf, admin_user):
        company = CompanyFactory(status=CompanyStatus.PENDING)
        request = rf.post("/admin/jobs/company/")
        request.user = admin_user
        request.session = {}
        request._messages = FallbackStorage(request)

        queryset = Company.objects.filter(pk=company.pk)
        admin_instance = CompanyAdmin(Company, None)
        admin_instance.approve_companies(request, queryset)

        assert Company.objects.get(pk=company.pk).status == CompanyStatus.APPROVED

    def test_approve_does_not_change_already_approved(self, rf, admin_user):
        company = CompanyFactory(status=CompanyStatus.APPROVED)
        request = rf.post("/admin/jobs/company/")
        request.user = admin_user
        request.session = {}
        request._messages = FallbackStorage(request)

        queryset = Company.objects.filter(pk=company.pk)
        admin_instance = CompanyAdmin(Company, None)
        admin_instance.approve_companies(request, queryset)

        # APPROVED não é PENDING, então filter(status=PENDING) retorna 0 atualizações
        assert Company.objects.get(pk=company.pk).status == CompanyStatus.APPROVED

    def test_approve_shows_success_message(self, rf, admin_user):
        CompanyFactory(status=CompanyStatus.PENDING)
        request = rf.post("/admin/jobs/company/")
        request.user = admin_user
        request.session = {}
        request._messages = FallbackStorage(request)

        queryset = Company.objects.filter(status=CompanyStatus.PENDING)
        admin_instance = CompanyAdmin(Company, None)
        admin_instance.approve_companies(request, queryset)

        messages_list = list(request._messages)
        success_messages = [m for m in messages_list if m.level == message_constants.SUCCESS]
        assert len(success_messages) > 0
        assert "aprovada" in str(success_messages[0].message).lower()


@pytest.mark.django_db
class TestCompanyAdminBlockAction:
    """block_companies: muda status de PENDING/APPROVED para BLOCKED."""

    def test_block_pending_company_changes_status_to_blocked(self, rf, admin_user):
        company = CompanyFactory(status=CompanyStatus.PENDING)
        request = rf.post("/admin/jobs/company/")
        request.user = admin_user
        request.session = {}
        request._messages = FallbackStorage(request)

        queryset = Company.objects.filter(pk=company.pk)
        admin_instance = CompanyAdmin(Company, None)
        admin_instance.block_companies(request, queryset)

        assert Company.objects.get(pk=company.pk).status == CompanyStatus.BLOCKED

    def test_block_approved_company_changes_status_to_blocked(self, rf, admin_user):
        company = CompanyFactory(status=CompanyStatus.APPROVED)
        request = rf.post("/admin/jobs/company/")
        request.user = admin_user
        request.session = {}
        request._messages = FallbackStorage(request)

        queryset = Company.objects.filter(pk=company.pk)
        admin_instance = CompanyAdmin(Company, None)
        admin_instance.block_companies(request, queryset)

        assert Company.objects.get(pk=company.pk).status == CompanyStatus.BLOCKED

    def test_block_shows_warning_message(self, rf, admin_user):
        CompanyFactory(status=CompanyStatus.APPROVED)
        request = rf.post("/admin/jobs/company/")
        request.user = admin_user
        request.session = {}
        request._messages = FallbackStorage(request)

        queryset = Company.objects.filter(status=CompanyStatus.APPROVED)
        admin_instance = CompanyAdmin(Company, None)
        admin_instance.block_companies(request, queryset)

        messages_list = list(request._messages)
        warning_messages = [m for m in messages_list if m.level == message_constants.WARNING]
        assert len(warning_messages) > 0
        assert "bloqueada" in str(warning_messages[0].message).lower()
