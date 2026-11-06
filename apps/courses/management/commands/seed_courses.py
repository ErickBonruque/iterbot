"""Cria/atualiza os cursos do campus Santa Helena e seus termos de busca.

Os dados vêm de `apps.courses.catalog` (fonte única, também usada pela
migração `0006_apply_course_catalog`).
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.courses.catalog import COURSES, apply_catalog
from apps.courses.models import Area, Course, SearchTerm


class Command(BaseCommand):
    help = "Cria/atualiza cursos UTFPR Santa Helena e termos de busca a partir do catálogo"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Mostra o que seria aplicado, sem salvar",
        )
        parser.add_argument(
            "--prune",
            action="store_true",
            help=(
                "Remove termos dos cursos do catálogo que não estão nele — inclusive "
                "os criados pelo admin — e as vagas pré-buscadas desses termos"
            ),
        )

    def handle(self, *args, **options):
        if options["dry_run"]:
            for entry in COURSES:
                self.stdout.write(f"{entry['name']} ({entry['code']})")
                for row in entry["terms"]:
                    self.stdout.write(f"  - {row['label']}: {row['term']} [{row['scope']}]")
            return

        with transaction.atomic():
            stats = apply_catalog(
                Course, SearchTerm, Area, create_missing=True, prune=options["prune"]
            )
        self.stdout.write(self.style.SUCCESS(f"Catálogo aplicado: {stats}"))
