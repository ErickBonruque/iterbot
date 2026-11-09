"""Migração bot.0009: apaga senhas já coletadas pelo bot.

Antes da remoção do passo de senha, a senha que o aluno (ou a empresa) digitava
ficava em texto puro no `InteractionLog` e, no caso do aluno, também no
`flow_data` da conversa. A migração redige as mensagens recebidas logo depois de
um pedido de senha, tira `temp_password` do `flow_data` e move quem estava
parado no passo de senha para o passo de e-mail.
"""

from datetime import timedelta

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase
from django.utils import timezone


class PasswordScrubMigrationTests(TransactionTestCase):
    # users fixado junto: o estado histórico só de bot.0008 traria um
    # UserProfile antigo, sem colunas NOT NULL que a tabela real já tem.
    migrate_from = (("bot", "0008_alter_botmessage_key"), ("users", "0008_studentprofile"))
    migrate_to = (("bot", "0009_scrub_collected_passwords"), ("users", "0008_studentprofile"))

    def _migrate_to(self, targets):
        executor = MigrationExecutor(connection)
        executor.migrate(list(targets))
        executor.loader.build_graph()
        return executor.loader.project_state(list(targets)).apps

    def tearDown(self):
        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())

    def _log(self, log_model, user_id, kind, content, minutes):
        row = log_model.objects.create(user_id=user_id, message_type=kind, message_content=content)
        # created_at é auto_now_add: ajusta depois para fixar a ordem.
        log_model.objects.filter(pk=row.pk).update(
            created_at=timezone.now() - timedelta(minutes=60 - minutes)
        )
        return row.pk

    def test_scrubs_passwords_and_moves_password_step_to_email(self):
        old_apps = self._migrate_to(self.migrate_from)
        UserProfile = old_apps.get_model("users", "UserProfile")
        ConversationState = old_apps.get_model("bot", "ConversationState")
        InteractionLog = old_apps.get_model("bot", "InteractionLog")

        aluno = UserProfile.objects.create(phone_number="554500000001@c.us")
        parado = UserProfile.objects.create(phone_number="554500000002@c.us")
        sem_ra = UserProfile.objects.create(phone_number="554500000003@c.us")

        ConversationState.objects.create(
            user_id=aluno.id, current_action=None, flow_data={"x": 1, "temp_password": "s3nha"}
        )
        ConversationState.objects.create(
            user_id=parado.id,
            current_action="login_step_password",
            flow_data={"temp_ra": "a1234567", "temp_password": "s3nha"},
        )
        ConversationState.objects.create(
            user_id=sem_ra.id, current_action="login_step_password", flow_data={}
        )

        ra = self._log(InteractionLog, aluno.id, "RECEIVED", "a1234567", 1)
        self._log(InteractionLog, aluno.id, "SENT", "🔑 *Crie sua senha de acesso*", 2)
        senha = self._log(InteractionLog, aluno.id, "RECEIVED", "MinhaSenha123", 3)
        self._log(InteractionLog, aluno.id, "SENT", "🔐 Digite seu e-mail", 4)
        email = self._log(InteractionLog, aluno.id, "RECEIVED", "a@alunos.utfpr.edu.br", 5)
        self._log(InteractionLog, aluno.id, "SENT", "❌ RA ou senha incorretos.", 6)
        retry = self._log(InteractionLog, aluno.id, "RECEIVED", "OutraSenha", 7)

        new_apps = self._migrate_to(self.migrate_to)
        new_log = new_apps.get_model("bot", "InteractionLog")
        new_state = new_apps.get_model("bot", "ConversationState")

        contents = dict(new_log.objects.values_list("pk", "message_content"))
        self.assertEqual(contents[ra], "a1234567")
        self.assertEqual(contents[email], "a@alunos.utfpr.edu.br")
        self.assertNotIn("MinhaSenha123", contents.values())
        self.assertNotIn("OutraSenha", contents.values())
        self.assertNotEqual(contents[senha], "MinhaSenha123")
        self.assertNotEqual(contents[retry], "OutraSenha")

        states = {s.user_id: s for s in new_state.objects.all()}
        self.assertEqual(states[aluno.id].flow_data, {"x": 1})
        self.assertEqual(states[parado.id].current_action, "login_step_email")
        self.assertEqual(states[parado.id].flow_data, {"temp_ra": "a1234567"})
        self.assertIsNone(states[sem_ra.id].current_action)
