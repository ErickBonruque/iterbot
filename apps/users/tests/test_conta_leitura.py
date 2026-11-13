"""Conta do admin somente leitura (comando ``criar_conta_leitura``).

A conta vê o painel, mas não pode alterar nada nem mexer no WhatsApp do bot.
"""

import re
from io import StringIO
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from apps.jobs.models import Company, CompanyStatus


def _criar(*args) -> str:
    out = StringIO()
    call_command("criar_conta_leitura", *args, stdout=out)
    return out.getvalue()


def _senha(saida: str) -> str:
    return re.search(r"Senha .*: (\S+)", saida).group(1)


class CriarContaLeituraCommandTests(TestCase):
    def test_cria_staff_sem_superusuario_e_senha_que_funciona(self):
        saida = _criar("leitura")

        user = User.objects.get(username="leitura")
        self.assertTrue(user.is_staff)
        self.assertFalse(user.is_superuser)
        self.assertTrue(user.check_password(_senha(saida)))
        self.assertEqual(list(user.groups.values_list("name", flat=True)), ["Somente leitura"])

    def test_conta_nao_vira_perfil_de_aluno(self):
        from apps.users.models import UserProfile

        _criar("leitura")
        _criar("leitura2")  # duas contas sem --email não colidem no e-mail único

        self.assertFalse(UserProfile.objects.filter(user__username__startswith="leitura").exists())

    def test_so_ve_sem_alterar_e_sem_conversas(self):
        _criar("leitura")
        user = User.objects.get(username="leitura")

        self.assertTrue(user.has_perm("jobs.view_company"))
        self.assertTrue(user.has_perm("users.view_userprofile"))
        self.assertFalse(user.has_perm("jobs.change_company"))
        self.assertFalse(user.has_perm("jobs.change_job"))
        self.assertFalse(user.has_perm("bot.view_interactionlog"))
        self.assertFalse(user.has_perm("bot.view_conversationstate"))
        self.assertFalse(user.has_perm("auth.view_user"))

    def test_rodar_de_novo_mantem_a_senha(self):
        senha = _senha(_criar("leitura"))
        saida = _criar("leitura")

        self.assertNotIn("Senha (", saida)
        self.assertTrue(User.objects.get(username="leitura").check_password(senha))

    def test_nova_senha_troca_a_senha(self):
        antiga = _senha(_criar("leitura"))
        nova = _senha(_criar("leitura", "--nova-senha"))

        user = User.objects.get(username="leitura")
        self.assertNotEqual(antiga, nova)
        self.assertTrue(user.check_password(nova))

    def test_recusa_rebaixar_superusuario(self):
        User.objects.create_superuser("admin", "a@example.com", "x")

        with self.assertRaises(CommandError):
            _criar("admin")
        self.assertTrue(User.objects.get(username="admin").is_superuser)


class ContaLeituraNoAdminTests(TestCase):
    def setUp(self):
        _criar("leitura")
        self.client.force_login(User.objects.get(username="leitura"))
        self.company = Company.objects.create(
            nome="Empresa X", cnpj="11222333000181", email="x@example.com"
        )

    def test_ve_a_lista_de_empresas(self):
        response = self.client.get("/admin/jobs/company/")
        self.assertEqual(response.status_code, 200)

    def test_nao_aprova_empresa_pela_acao_em_lote(self):
        self.client.post(
            "/admin/jobs/company/",
            {"action": "approve_companies", "_selected_action": [self.company.pk]},
        )
        self.company.refresh_from_db()
        self.assertEqual(self.company.status, CompanyStatus.PENDING)

    def test_nao_edita_empresa(self):
        response = self.client.post(
            f"/admin/jobs/company/{self.company.pk}/change/", {"nome": "Outro nome"}
        )
        self.assertEqual(response.status_code, 403)

    def test_nao_dispara_coleta_pelo_endereco_direto(self):
        with patch("apps.jobs.tasks.fetch_daily_jobs.delay") as delay:
            response = self.client.get("/admin/jobs/dailyjob/trigger_fetch_daily_jobs/")
        self.assertEqual(response.status_code, 403)
        delay.assert_not_called()

    def test_nao_ve_conversas(self):
        response = self.client.get("/admin/bot/interactionlog/")
        self.assertEqual(response.status_code, 403)

    def test_nao_controla_o_whatsapp(self):
        with (
            patch("infra.waha.client.WahaClient.get_qr") as get_qr,
            patch("infra.waha.client.WahaClient.restart_session") as restart,
            patch("infra.waha.client.WahaClient.logout_session") as logout,
        ):
            self.assertEqual(self.client.get("/admin/api/waha-qr/").status_code, 403)
            self.assertEqual(self.client.post("/admin/api/waha-restart/").status_code, 403)
            self.assertEqual(self.client.post("/admin/api/waha-logout/").status_code, 403)
        get_qr.assert_not_called()
        restart.assert_not_called()
        logout.assert_not_called()

    def test_status_do_bot_sem_botoes_de_pareamento(self):
        response = self.client.get("/admin/status-bot/")
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Mostrar QR Code")
        self.assertNotContains(response, "Desconectar número")


class SuperusuarioMantemPareamentoTests(TestCase):
    def test_status_do_bot_com_botoes_de_pareamento(self):
        self.client.force_login(User.objects.create_superuser("admin", "a@example.com", "x"))
        response = self.client.get("/admin/status-bot/")
        self.assertContains(response, "Mostrar QR Code")
