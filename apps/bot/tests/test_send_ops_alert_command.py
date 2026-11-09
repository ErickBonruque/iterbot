"""`manage.py send_ops_alert`: alerta operacional por e-mail para scripts do host.

Usado pelo backup diário (deployment/scripts/backup-postgres.sh) quando algo
falha — reaproveita o provider de e-mail configurado e o ALERT_EMAIL.
"""

from io import StringIO
from unittest.mock import patch

from django.core.management import CommandError, call_command
from django.test import SimpleTestCase


class SendOpsAlertCommandTests(SimpleTestCase):
    @patch("apps.bot.management.commands.send_ops_alert.send_transactional_email")
    def test_sends_subject_and_body_to_alert_email(self, mock_send):
        mock_send.return_value = {"status": "sent", "provider": "smtp"}

        call_command(
            "send_ops_alert",
            "--subject",
            "Backup falhou",
            "--body",
            "pg_dump saiu 1",
            stdout=StringIO(),
        )

        kwargs = mock_send.call_args.kwargs
        self.assertEqual(kwargs["subject"], "[IterBot] Backup falhou")
        self.assertEqual(kwargs["message"], "pg_dump saiu 1")
        self.assertEqual(kwargs["event_type"], "ops_alert")
        self.assertEqual(len(kwargs["recipient_list"]), 1)

    @patch("apps.bot.management.commands.send_ops_alert.send_transactional_email")
    def test_fails_loudly_when_email_is_not_sent(self, mock_send):
        mock_send.return_value = {"status": "failed", "provider": "smtp", "error_code": "x"}

        with self.assertRaises(CommandError):
            call_command("send_ops_alert", "--subject", "s", "--body", "b", stdout=StringIO())
