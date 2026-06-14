from django.contrib.auth.models import User
from django.db import models

from apps.core.models import TimeStampedModel
from infra.security.fields import EncryptedCharField


class UserProfile(TimeStampedModel):
    """
    Representa um usuário do sistema, vinculado ao número de telefone (WAHA ID).
    Armazena credenciais da UTFPR (criptografadas idealmente, aqui simplificado para MVP).
    """

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="profile",
        help_text="Vínculo com django.contrib.auth.User para autenticação web",
    )
    phone_number = models.CharField(
        max_length=50, unique=True, help_text="ID do usuário no WhatsApp (ex: 554199999999@c.us)"
    )
    email = models.EmailField(
        unique=True, blank=True, null=True, help_text="E-mail do aluno (@alunos.utfpr.edu.br)"
    )
    email_verified = models.BooleanField(
        default=False, help_text="Indica se o email institucional foi confirmado via token"
    )
    email_confirmation_token = models.CharField(
        max_length=64,
        null=True,
        blank=True,
        unique=True,
        help_text="Token UUID para confirmação de email",
    )
    email_confirmation_sent_at = models.DateTimeField(
        null=True, blank=True, help_text="Data/hora do último envio de email de confirmação"
    )
    password = models.CharField(
        max_length=128,
        blank=True,
        null=True,
        help_text="Senha hash (Django User integração futura)",
    )
    ra = models.CharField(max_length=20, blank=True, null=True, help_text="Registro Acadêmico")
    utfpr_password = EncryptedCharField(
        max_length=512, blank=True, null=True, help_text="Senha do Portal (criptografada)"
    )
    is_authenticated_utfpr = models.BooleanField(default=False)
    course = models.ForeignKey(
        "courses.Course",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="preferred_by",
        help_text="Curso preferido do aluno (salvo automaticamente na 1ª busca)",
    )

    # Campos de autenticação empresa via WhatsApp
    company = models.ForeignKey(
        "jobs.Company",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="whatsapp_users",
        help_text="Empresa vinculada a este número WhatsApp",
    )
    is_company_authenticated = models.BooleanField(
        default=False,
        help_text="Indica se este número está autenticado como empresa",
    )
    company_confirmation_token = models.CharField(
        max_length=64,
        null=True,
        blank=True,
        unique=True,
        help_text="Token para confirmar vínculo WhatsApp-empresa via email",
    )
    company_confirmation_sent_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Data/hora do envio do email de confirmação de empresa",
    )

    last_activity = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.phone_number} ({self.ra if self.ra else 'Sem RA'})"


class StudentProfile(TimeStampedModel):
    """Mini-perfil do aluno, coletado no bot e reutilizável entre candidaturas.

    Mantido separado do `UserProfile` (que guarda identidade/credenciais) por ser
    uma preocupação distinta: dados que o aluno consente em compartilhar com as
    empresas ao se candidatar. Por isso **não** usa `EncryptedCharField` — esse
    conteúdo é exibido à empresa por design (no portal/e-mail); apenas evitamos
    logar o conteúdo (structlog usa IDs, não os campos).
    """

    user = models.OneToOneField(
        UserProfile,
        on_delete=models.CASCADE,
        related_name="student_profile",
        help_text="Aluno dono do mini-perfil",
    )
    periodo = models.CharField(
        max_length=40, blank=True, help_text="Período/semestre atual do aluno"
    )
    skills = models.TextField(blank=True, help_text="Principais habilidades/competências")
    linkedin_url = models.URLField(blank=True, help_text="Perfil do LinkedIn")
    cv_url = models.URLField(blank=True, help_text="Link para currículo/portfólio")
    bio = models.TextField(blank=True, help_text="Breve apresentação")

    class Meta:
        verbose_name = "Mini-perfil do aluno"
        verbose_name_plural = "Mini-perfis dos alunos"

    def __str__(self):
        return f"Perfil de {self.user}"

    @property
    def is_complete(self) -> bool:
        """Perfil utilizável para candidatura: período e skills preenchidos."""
        return bool(self.periodo and self.skills)

    def to_snapshot(self) -> dict:
        """Congela o perfil para anexar à candidatura (histórico imutável)."""
        return {
            "periodo": self.periodo,
            "skills": self.skills,
            "linkedin_url": self.linkedin_url,
            "cv_url": self.cv_url,
            "bio": self.bio,
        }
