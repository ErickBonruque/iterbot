from django.contrib.auth.models import User
from django.db import models

from apps.core.models import TimeStampedModel
from apps.courses.models import Course, SearchTerm
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
    last_activity = models.DateTimeField(auto_now=True)
    current_action = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        help_text="Estado atual do fluxo conversacional do bot",
    )
    selected_course = models.ForeignKey(
        Course,
        related_name="selected_by_users",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
    )
    selected_term = models.ForeignKey(
        SearchTerm,
        related_name="selected_by_users",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
    )
    flow_data = models.JSONField(
        default=dict, blank=True, help_text="Dados temporários do fluxo conversacional"
    )

    def __str__(self):
        return f"{self.phone_number} ({self.ra if self.ra else 'Sem RA'})"
