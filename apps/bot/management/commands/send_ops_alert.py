"""Alerta operacional por e-mail, para scripts que rodam no host (cron).

Ex.: docker exec iterbot_backend python manage.py send_ops_alert \
        --subject "Backup falhou" --body "pg_dump saiu com código 1"
"""

from django.core.management.base import BaseCommand, CommandError

from apps.bot.email_service import ALERT_EMAIL, send_transactional_email


class Command(BaseCommand):
    help = "Envia um alerta operacional para ALERT_EMAIL pelo provider de e-mail configurado"

    def add_arguments(self, parser):
        parser.add_argument("--subject", required=True)
        parser.add_argument("--body", required=True)

    def handle(self, *args, **options):
        result = send_transactional_email(
            subject=f"[IterBot] {options['subject']}",
            message=options["body"],
            recipient_list=[ALERT_EMAIL],
            event_type="ops_alert",
        )
        if result.get("status") != "sent":
            raise CommandError(f"alerta nao enviado: {result.get('error_code')}")
        self.stdout.write("alerta enviado")
