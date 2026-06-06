"""
Seed courses and search terms for UTFPR Santa Helena.
Covers: Ciência da Computação, Agronomia, Ciências Biológicas.
"""

from django.core.management.base import BaseCommand

from apps.courses.models import Course, SearchTerm

COURSES = [
    {
        "name": "Ciência da Computação",
        "code": "COENS",
        "level": "Graduação",
        "modality": "Presencial",
        "is_active": True,
        "order": 1,
    },
    {
        "name": "Agronomia",
        "code": "COAGR",
        "level": "Graduação",
        "modality": "Presencial",
        "is_active": True,
        "order": 2,
    },
    {
        "name": "Ciências Biológicas",
        "code": "COBIO",
        "level": "Graduação",
        "modality": "Presencial",
        "is_active": True,
        "order": 3,
    },
]

# (term, location, is_remote, distance, site_name, job_type, priority, hours_old)
COMPUTACAO_TERMS = [
    (
        "estágio desenvolvimento de software",
        "Brasil",
        True,
        None,
        "indeed,linkedin,glassdoor",
        None,
        10,
        72,
    ),
    ("estágio desenvolvedor", "Brasil", True, None, "indeed,linkedin,glassdoor", None, 10, 72),
    ("estágio programação", "Brasil", True, None, "indeed,linkedin", None, 9, 72),
    ("estágio análise de dados", "Brasil", True, None, "indeed,linkedin,glassdoor", None, 8, 72),
    ("estágio ciência de dados", "Brasil", True, None, "indeed,linkedin", None, 8, 72),
    ("estágio front-end", "Curitiba, PR", False, None, "indeed,linkedin", None, 7, 72),
    ("estágio back-end", "Curitiba, PR", False, None, "indeed,linkedin", None, 7, 72),
    ("estágio QA testes de software", "Brasil", True, None, "indeed,linkedin", None, 6, 72),
    (
        "estágio suporte e infraestrutura TI",
        "Curitiba, PR",
        False,
        None,
        "indeed,glassdoor",
        None,
        6,
        72,
    ),
    ("software engineer intern", "Brasil", True, None, "linkedin", "internship", 5, 72),
    ("data science intern", "Brasil", True, None, "linkedin", "internship", 5, 72),
    ("estágio DevOps cloud", "Brasil", True, None, "indeed,linkedin", None, 5, 72),
]

AGRONOMIA_TERMS = [
    ("estágio agronomia", "Toledo, PR", False, 60, "indeed,linkedin,glassdoor", None, 10, 168),
    ("estágio engenheiro agrônomo", "Cascavel, PR", False, 60, "indeed,linkedin", None, 10, 168),
    (
        "estágio assistência técnica agrícola",
        "Marechal Cândido Rondon, PR",
        False,
        60,
        "indeed,linkedin",
        None,
        9,
        168,
    ),
    ("estágio agronegócio", "Toledo, PR", False, 60, "indeed,glassdoor", None, 8, 168),
    ("estágio cooperativa agrícola", "Cascavel, PR", False, 70, "indeed,linkedin", None, 8, 168),
    ("estágio produção vegetal", "Santa Helena, PR", False, 70, "indeed", None, 7, 168),
    ("estágio fitossanidade", "Toledo, PR", False, 60, "indeed,linkedin", None, 7, 168),
    ("estágio agricultura de precisão", "Cascavel, PR", False, 70, "indeed,linkedin", None, 6, 168),
    ("estágio solos e fertilidade", "Toledo, PR", False, 60, "indeed", None, 6, 168),
    (
        "estágio pesquisa agrícola",
        "Marechal Cândido Rondon, PR",
        False,
        60,
        "indeed,linkedin",
        None,
        5,
        168,
    ),
    ("estágio agronomia remoto", "Brasil", True, None, "indeed,linkedin", None, 4, 168),
]

BIOLOGIA_TERMS = [
    (
        "estágio ciências biológicas",
        "Toledo, PR",
        False,
        70,
        "indeed,linkedin,glassdoor",
        None,
        10,
        168,
    ),
    ("estágio biólogo", "Cascavel, PR", False, 70, "indeed,linkedin", None, 10, 168),
    ("estágio meio ambiente", "Toledo, PR", False, 70, "indeed,linkedin", None, 9, 168),
    (
        "estágio análises clínicas laboratório",
        "Cascavel, PR",
        False,
        60,
        "indeed,glassdoor",
        None,
        8,
        168,
    ),
    (
        "estágio educação ambiental",
        "Marechal Cândido Rondon, PR",
        False,
        70,
        "indeed",
        None,
        8,
        168,
    ),
    ("estágio microbiologia", "Cascavel, PR", False, 70, "indeed,linkedin", None, 7, 168),
    (
        "estágio controle de qualidade alimentos",
        "Toledo, PR",
        False,
        60,
        "indeed,linkedin",
        None,
        7,
        168,
    ),
    ("estágio gestão ambiental", "Cascavel, PR", False, 70, "indeed,glassdoor", None, 6, 168),
    ("estágio biotecnologia", "Toledo, PR", False, 70, "indeed,linkedin", None, 6, 168),
    ("estágio docência ciências", "Santa Helena, PR", False, 80, "indeed", None, 5, 168),
    ("estágio vigilância sanitária", "Cascavel, PR", False, 60, "indeed", None, 5, 168),
    ("estágio biologia remoto", "Brasil", True, None, "indeed,linkedin", None, 4, 168),
]

TERMS_BY_COURSE_CODE = {
    "COENS": COMPUTACAO_TERMS,
    "COAGR": AGRONOMIA_TERMS,
    "COBIO": BIOLOGIA_TERMS,
}


class Command(BaseCommand):
    help = "Seed cursos UTFPR Santa Helena e termos de busca JobSpy"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Simula a operação sem salvar no banco",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        if dry_run:
            self.stdout.write(self.style.WARNING("Modo DRY RUN — nada será salvo\n"))

        courses_created = 0
        terms_created = 0
        terms_skipped = 0

        for course_data in COURSES:
            code = course_data["code"]
            terms = TERMS_BY_COURSE_CODE[code]

            if dry_run:
                self.stdout.write(f"[DRY] Criaria curso: {course_data['name']} ({code})")
                for term_row in terms:
                    self.stdout.write(f"  [DRY] Termo: {term_row[0]}")
                continue

            course, created = Course.objects.get_or_create(
                code=code,
                defaults={k: v for k, v in course_data.items() if k != "code"},
            )
            if created:
                courses_created += 1
                self.stdout.write(self.style.SUCCESS(f"  Curso criado: {course.name}"))
            else:
                self.stdout.write(f"  Curso existente: {course.name}")

            top_priority = max(t[6] for t in terms)  # priority está no índice 6 da tupla

            for (
                term,
                location,
                is_remote,
                distance,
                site_name,
                job_type,
                priority,
                hours_old,
            ) in terms:
                is_default = priority == top_priority
                _, term_created = SearchTerm.objects.get_or_create(
                    course=course,
                    term=term,
                    defaults={
                        "location": location,
                        "is_remote": is_remote,
                        "distance": distance,
                        "site_name": site_name,
                        "job_type": job_type,
                        "priority": priority,
                        "hours_old": hours_old,
                        "results_wanted": 15,
                        "offset": 0,
                        "country_indeed": "Brazil",
                        "linkedin_fetch_description": False,
                        "is_default": is_default,
                    },
                )
                if term_created:
                    terms_created += 1
                    self.stdout.write(f"    + Termo: {term}")
                else:
                    terms_skipped += 1

        if not dry_run:
            self.stdout.write(
                self.style.SUCCESS(
                    f"\nConcluído: {courses_created} cursos criados, "
                    f"{terms_created} termos criados, {terms_skipped} já existiam."
                )
            )
