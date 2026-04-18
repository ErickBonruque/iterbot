from django.core.exceptions import ValidationError
from validate_docbr import CNPJ  # - external library usa CNPJ como nome de classe


def validate_cnpj(value):
    """
    Valida CNPJ usando validate-docbr.
    Aceita CNPJ com ou sem máscara.
    """
    validator = CNPJ()
    if not validator.validate(value):
        raise ValidationError(
            "CNPJ inválido. Verifique os dígitos verificadores.", code="invalid_cnpj"
        )
