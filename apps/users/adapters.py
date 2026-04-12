from allauth.account.adapter import DefaultAccountAdapter
from django.core.exceptions import ValidationError

from apps.users.validators import validate_utfpr_email


class UTFPRAccountAdapter(DefaultAccountAdapter):
    """
    Adapter customizado do django-allauth para validar domínio de e-mail UTFPR.
    """

    def clean_email(self, email):
        """
        Valida que o e-mail pertence ao domínio @alunos.utfpr.edu.br.
        """
        email = super().clean_email(email)
        validate_utfpr_email(email)
        return email
