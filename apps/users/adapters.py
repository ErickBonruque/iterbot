from allauth.account.adapter import DefaultAccountAdapter

from apps.users.validators import validate_utfpr_email


class UTFPRAccountAdapter(DefaultAccountAdapter):
    """
    Adapter customizado do django-allauth para validar dominio de e-mail.
    - Rotas de alunos (/accounts/): restringe a @alunos.utfpr.edu.br
    - Rotas de empresas (/empresas/): permite qualquer e-mail
    """

    def clean_email(self, email):
        """
        Valida e-mail condicionalmente baseado na rota de origem.
        """
        email = super().clean_email(email)
        # Rotas de empresa nao tem restricao de dominio
        if hasattr(self, 'request') and self.request and self.request.path.startswith('/empresas/'):
            return email
        validate_utfpr_email(email)
        return email
