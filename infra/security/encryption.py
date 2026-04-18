"""Encryption utilities for sensitive data."""

import base64

from cryptography.fernet import Fernet
from django.conf import settings


class FieldEncryption:
    """Handles encryption and decryption of sensitive database fields.

    Attributes:
        _fernet: Fernet cipher instance for encrypt/decrypt operations.
    """

    def __init__(self) -> None:
        """Initialize with encryption key derived from Django SECRET_KEY."""
        key_material = settings.SECRET_KEY.encode()[:32].ljust(32, b"0")
        self._key = base64.urlsafe_b64encode(key_material)
        self._fernet = Fernet(self._key)

    def encrypt(self, plaintext: str) -> str:
        """Encrypt a plaintext string.

        Args:
            plaintext: The string to encrypt.

        Returns:
            Base64-encoded encrypted string.
        """
        if not plaintext:
            return ""

        encrypted_bytes = self._fernet.encrypt(plaintext.encode())
        return encrypted_bytes.decode()

    def decrypt(self, ciphertext: str) -> str:
        """Decrypt an encrypted string.

        Args:
            ciphertext: The encrypted string to decrypt.

        Returns:
            Decrypted plaintext string, or empty string on failure.
        """
        if not ciphertext:
            return ""

        try:
            decrypted_bytes = self._fernet.decrypt(ciphertext.encode())
            return decrypted_bytes.decode()
        except Exception:
            return ""


_encryptor: FieldEncryption | None = None


def get_encryptor() -> FieldEncryption:
    """Get or create the global encryptor instance.

    Returns:
        The global FieldEncryption singleton.
    """
    global _encryptor
    if _encryptor is None:
        _encryptor = FieldEncryption()
    return _encryptor


def encrypt_field(value: str) -> str:
    """Convenience function to encrypt a field value.

    Args:
        value: The plaintext string to encrypt.

    Returns:
        Base64-encoded encrypted string.
    """
    return get_encryptor().encrypt(value)


def decrypt_field(value: str) -> str:
    """Convenience function to decrypt a field value.

    Args:
        value: The encrypted string to decrypt.

    Returns:
        Decrypted plaintext string, or empty string on failure.
    """
    return get_encryptor().decrypt(value)
