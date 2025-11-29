"""Custom Django model fields with encryption."""
from typing import Any, Optional

from django.db import models

from .encryption import decrypt_field, encrypt_field


class EncryptedCharField(models.CharField):
    """CharField that automatically encrypts/decrypts data."""

    description = "Encrypted CharField"

    def from_db_value(
        self, value: Optional[str], expression: Any, connection: Any
    ) -> Optional[str]:
        """Decrypt value when loading from database."""
        if value is None:
            return value
        return decrypt_field(value)

    def to_python(self, value: Optional[str]) -> Optional[str]:
        """Convert value to Python string."""
        if isinstance(value, str) or value is None:
            return value
        return str(value)

    def get_prep_value(self, value: Optional[str]) -> Optional[str]:
        """Encrypt value before saving to database."""
        if value is None:
            return value
        # Only encrypt if not already encrypted (simple check)
        # In production, you might want a more robust check
        return encrypt_field(str(value))


class EncryptedTextField(models.TextField):
    """TextField that automatically encrypts/decrypts data."""

    description = "Encrypted TextField"

    def from_db_value(
        self, value: Optional[str], expression: Any, connection: Any
    ) -> Optional[str]:
        """Decrypt value when loading from database."""
        if value is None:
            return value
        return decrypt_field(value)

    def to_python(self, value: Optional[str]) -> Optional[str]:
        """Convert value to Python string."""
        if isinstance(value, str) or value is None:
            return value
        return str(value)

    def get_prep_value(self, value: Optional[str]) -> Optional[str]:
        """Encrypt value before saving to database."""
        if value is None:
            return value
        return encrypt_field(str(value))
