from django.core.exceptions import ValidationError
from validate_docbr import CNPJ as CNPJValidator


def validate_cnpj(value):
    """
    Valida CNPJ usando validate-docbr.
    Aceita CNPJ com ou sem máscara.
    """
    cnpj_validator = CNPJValidator()
    if not cnpj_validator.validate(value):
        raise ValidationError(
            'CNPJ inválido. Verifique os dígitos verificadores.',
            code='invalid_cnpj'
        )
