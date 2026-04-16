"""Custom Django model fields with encryption."""
from typing import Any, Optional

from django.db import models

from .encryption import decrypt_field, encrypt_field


class EncryptedCharField(models.CharField):
    """CharField that automatically encrypts/decrypts data.

    Attributes:
        description: Field description for Django introspection.
    """

    description = "Encrypted CharField"

    def from_db_value(
        self, value: Optional[str], expression: Any, connection: Any
    ) -> Optional[str]:
        """Decrypt value when loading from database.

        Args:
            value: Raw value from database.
            expression: Database expression.
            connection: Database connection.

        Returns:
            Decrypted string or None.
        """
        if value is None:
            return value
        return decrypt_field(value)

    def to_python(self, value: Optional[str]) -> Optional[str]:
        """Convert value to Python string.

        Args:
            value: Value to convert.

        Returns:
            String value or None.
        """
        if isinstance(value, str) or value is None:
            return value
        return str(value)

    def get_prep_value(self, value: Optional[str]) -> Optional[str]:
        """Encrypt value before saving to database.

        Args:
            value: Python value to prepare for DB.

        Returns:
            Encrypted string or None.
        """
        if value is None:
            return value
        return encrypt_field(str(value))


class EncryptedTextField(models.TextField):
    """TextField that automatically encrypts/decrypts data.

    Attributes:
        description: Field description for Django introspection.
    """

    description = "Encrypted TextField"

    def from_db_value(
        self, value: Optional[str], expression: Any, connection: Any
    ) -> Optional[str]:
        """Decrypt value when loading from database.

        Args:
            value: Raw value from database.
            expression: Database expression.
            connection: Database connection.

        Returns:
            Decrypted string or None.
        """
        if value is None:
            return value
        return decrypt_field(value)

    def to_python(self, value: Optional[str]) -> Optional[str]:
        """Convert value to Python string.

        Args:
            value: Value to convert.

        Returns:
            String value or None.
        """
        if isinstance(value, str) or value is None:
            return value
        return str(value)

    def get_prep_value(self, value: Optional[str]) -> Optional[str]:
        """Encrypt value before saving to database.

        Args:
            value: Python value to prepare for DB.

        Returns:
            Encrypted string or None.
        """
        if value is None:
            return value
        return encrypt_field(str(value))
