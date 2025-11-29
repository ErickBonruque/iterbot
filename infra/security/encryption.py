"""Encryption utilities for sensitive data."""
import base64
from typing import Optional

from cryptography.fernet import Fernet
from django.conf import settings


class FieldEncryption:
    """Handles encryption and decryption of sensitive database fields."""

    def __init__(self) -> None:
        """Initialize with encryption key derived from Django SECRET_KEY."""
        # Derive a Fernet key from Django's SECRET_KEY
        # In production, consider using a separate encryption key
        key_material = settings.SECRET_KEY.encode()[:32].ljust(32, b"0")
        self._key = base64.urlsafe_b64encode(key_material)
        self._fernet = Fernet(self._key)

    def encrypt(self, plaintext: str) -> str:
        """
        Encrypt a plaintext string.
        
        Args:
            plaintext: The string to encrypt
            
        Returns:
            Base64-encoded encrypted string
        """
        if not plaintext:
            return ""
        
        encrypted_bytes = self._fernet.encrypt(plaintext.encode())
        return encrypted_bytes.decode()

    def decrypt(self, ciphertext: str) -> str:
        """
        Decrypt an encrypted string.
        
        Args:
            ciphertext: The encrypted string to decrypt
            
        Returns:
            Decrypted plaintext string
        """
        if not ciphertext:
            return ""
        
        try:
            decrypted_bytes = self._fernet.decrypt(ciphertext.encode())
            return decrypted_bytes.decode()
        except Exception:
            # If decryption fails, return empty string
            # This can happen with legacy unencrypted data
            return ""


# Global instance
_encryptor: Optional[FieldEncryption] = None


def get_encryptor() -> FieldEncryption:
    """Get or create the global encryptor instance."""
    global _encryptor
    if _encryptor is None:
        _encryptor = FieldEncryption()
    return _encryptor


def encrypt_field(value: str) -> str:
    """Convenience function to encrypt a field value."""
    return get_encryptor().encrypt(value)


def decrypt_field(value: str) -> str:
    """Convenience function to decrypt a field value."""
    return get_encryptor().decrypt(value)
