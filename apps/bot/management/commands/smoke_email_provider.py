"""Smoke local para validar contrato do provider de email."""

from django.core.management.base import BaseCommand, CommandError

from config.env import settings
from infra.email.factory import get_email_provider


class Command(BaseCommand):
    help = "Valida wiring e contrato do provider de email sem chamada externa obrigatoria"

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Executa smoke com provider fake")

    def handle(self, *args, **options):
        expected_keys = {"status", "provider", "message_id", "error_code"}
        is_dry_run = options["dry_run"]

        provider_name = settings.email.provider
        if not provider_name:
            raise CommandError("EMAIL_PROVIDER ausente")

        if is_dry_run:
            result = {
                "status": "sent",
                "provider": provider_name,
                "message_id": "dry-run-message-id",
                "error_code": None,
            }
        else:
            provider = get_email_provider(provider_name=provider_name)
            send_result = provider.send(
                subject="[Smoke] Provider de email",
                message="Smoke de contrato do provider",
                from_email=settings.email.from_email,
                recipient_list=[settings.email.from_email],
            )
            result = send_result.to_dict()

        result_keys = set(result.keys())
        missing_keys = expected_keys - result_keys
        if missing_keys:
            raise CommandError(
                f"Contrato invalido: chaves ausentes {', '.join(sorted(missing_keys))}"
            )

        self.stdout.write(self.style.SUCCESS(f"Smoke OK: {result}"))
