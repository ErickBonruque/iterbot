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

    course = models.ForeignKey(Course, related_name="search_terms", on_delete=models.CASCADE)
    term = models.CharField(max_length=100, help_text="Termo de busca para vagas")
    is_default = models.BooleanField(default=True, help_text="Termo padrão/ativo")
    priority = models.IntegerField(
        default=0, help_text="Prioridade na busca (maior = mais importante)"
    )

    class Meta:
        ordering = ["-priority", "term"]
        verbose_name = "Termo de Busca"
        verbose_name_plural = "Termos de Busca"
        unique_together = [["course", "term"]]

    def __str__(self):
        return f"{self.term} ({self.course.name})"
