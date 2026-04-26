from django.db import models

from apps.core.models import TimeStampedModel


class Course(TimeStampedModel):
    """
    Representa um curso da UTFPR ou área de interesse.
    """

    name = models.CharField(max_length=100, help_text="Nome do curso")
    code = models.CharField(
        max_length=20, blank=True, null=True, help_text="Código do curso (ex: COENS)"
    )
    description = models.TextField(blank=True, null=True, help_text="Descrição detalhada do curso")
    is_active = models.BooleanField(default=True, help_text="Curso ativo no sistema")
    order = models.IntegerField(default=0, help_text="Ordem de exibição")
    level = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        help_text="Nível do curso (ex: Graduação, Pós-graduação)",
    )
    modality = models.CharField(
        max_length=50, blank=True, null=True, help_text="Modalidade do curso (ex: Presencial, EAD)"
    )
    duration = models.IntegerField(blank=True, null=True, help_text="Duração do curso em semestres")

    class Meta:
        ordering = ["order", "name"]
        verbose_name = "Curso"
        verbose_name_plural = "Cursos"

    def __str__(self):
        return self.name


class SearchTerm(TimeStampedModel):
    """
    Termos de busca associados a um curso para usar no JobSpy.
    Ex: Curso 'Engenharia de Software' -> Termos 'Python', 'Django', 'Estágio TI'.
    """

    JOB_TYPE_CHOICES = [
        ("fulltime", "Tempo Integral"),
        ("parttime", "Meio Período"),
        ("internship", "Estágio"),
        ("contract", "Contrato"),
        ("temporary", "Temporário"),
        ("other", "Outro"),
    ]
    COUNTRY_CHOICES = [
        ("Brazil", "Brasil"),
        ("USA", "Estados Unidos"),
        ("Argentina", "Argentina"),
        ("Canada", "Canadá"),
        ("Portugal", "Portugal"),
        ("UK", "Reino Unido"),
        ("Australia", "Austrália"),
        ("Germany", "Alemanha"),
        ("France", "França"),
        ("Spain", "Espanha"),
        ("Mexico", "México"),
        ("Chile", "Chile"),
    ]

    course = models.ForeignKey(Course, related_name="search_terms", on_delete=models.CASCADE)
    term = models.CharField(max_length=100, help_text="Termo de busca para vagas")
    is_default = models.BooleanField(default=True, help_text="Termo padrão/ativo")
    priority = models.IntegerField(
        default=0, help_text="Prioridade na busca (maior = mais importante)"
    )

    site_name = models.CharField(
        max_length=100,
        default="linkedin,indeed,glassdoor",
        help_text="Sites de busca separados por vírgula: linkedin, indeed, glassdoor, zip_recruiter, google",
    )
    location = models.CharField(
        max_length=100,
        default="Curitiba, PR",
        help_text="Localização geográfica da busca",
    )
    distance = models.IntegerField(
        blank=True,
        null=True,
        help_text="Distância em milhas do local de busca (padrão jobspy: 50)",
    )
    job_type = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        choices=JOB_TYPE_CHOICES,
        help_text="Tipo de vaga",
    )
    is_remote = models.BooleanField(
        default=False,
        help_text="Filtrar apenas vagas remotas",
    )
    results_wanted = models.IntegerField(
        default=10,
        help_text="Número máximo de vagas por termo de busca",
    )
    hours_old = models.IntegerField(
        default=72,
        help_text="Considerar vagas publicadas nas últimas N horas",
    )
    country_indeed = models.CharField(
        max_length=50,
        default="Brazil",
        choices=COUNTRY_CHOICES,
        help_text="País para busca no Indeed e Glassdoor",
    )
    linkedin_fetch_description = models.BooleanField(
        default=False,
        help_text="Buscar descrição completa no LinkedIn (aumenta o tempo de busca)",
    )
    linkedin_company_ids = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="IDs de empresas no LinkedIn separados por vírgula (ex: 123456,789012)",
    )
    offset = models.IntegerField(
        default=0,
        help_text="Offset para paginação dos resultados de busca",
    )

    class Meta:
        ordering = ["-priority", "term"]
        verbose_name = "Termo de Busca"
        verbose_name_plural = "Termos de Busca"
        unique_together = [["course", "term"]]

    def __str__(self):
        return f"{self.term} ({self.course.name})"

    def to_search_kwargs(self, limit_override: int | None = None) -> dict:
        """Retorna kwargs completos para `JobSearchService.search()` derivados
        deste SearchTerm.

        Uso central para garantir que admin e bot apliquem exatamente a mesma
        configuração (location, hours_old, is_remote, job_type, country_indeed,
        site_name, linkedin_*) — antes o bot ignorava tudo e usava defaults
        hardcoded, divergindo da busca executada no "Testar busca" do admin.

        Args:
            limit_override: Se informado, sobrescreve `results_wanted` (o bot
                limita em 5 por UX do WhatsApp).
        """
        site_list = [s.strip() for s in (self.site_name or "").split(",") if s.strip()]

        company_ids: list[int] | None = None
        if self.linkedin_company_ids:
            try:
                company_ids = [
                    int(i.strip()) for i in self.linkedin_company_ids.split(",") if i.strip()
                ]
            except ValueError:
                company_ids = None

        return {
            "location": self.location,
            "limit": limit_override if limit_override is not None else self.results_wanted,
            "hours_old": self.hours_old,
            "site_name": site_list or None,
            "distance": self.distance,
            "job_type": self.job_type or None,
            "is_remote": self.is_remote,
            "country_indeed": self.country_indeed,
            "linkedin_fetch_description": self.linkedin_fetch_description,
            "linkedin_company_ids": company_ids,
            "offset": self.offset,
        }
