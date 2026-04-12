from django.core.exceptions import ValidationError


def validate_utfpr_email(email: str) -> None:
    """
    Valida se o e-mail pertence ao domínio @alunos.utfpr.edu.br.
    
    Raises:
        ValidationError: Se o e-mail não for do domínio institucional.
    """
    if not email.endswith("@alunos.utfpr.edu.br"):
        raise ValidationError(
            "Apenas e-mails @alunos.utfpr.edu.br são aceitos.",
            code="invalid_email_domain",
        )
