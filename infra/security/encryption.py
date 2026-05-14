"""Encryption utilities for sensitive data."""

import base64
import logging

from cryptography.fernet import Fernet, InvalidToken, MultiFernet
from django.conf import settings

logger = logging.getLogger(__name__)


def _build_fernet_key(raw: str) -> bytes:
    """Deriva uma chave Fernet de 32 bytes a partir de uma string arbitrária."""
    material = raw.encode()[:32].ljust(32, b"0")
    return base64.urlsafe_b64encode(material)


def _make_fernet() -> Fernet | MultiFernet:
    """Constrói o objeto Fernet (ou MultiFernet para rotação de chave).

    Prioridade:
    1. ``ENCRYPTION_KEY`` — chave dedicada (valor bruto de 32 bytes ou Fernet URL-safe base64).
       Quando presente é usada como chave primária de criptografia.
    2. ``SECRET_KEY`` — fallback para retrocompatibilidade com dados cifrados antes de
       ``ENCRYPTION_KEY`` ser introduzida.

    Se apenas ``ENCRYPTION_KEY`` estiver configurada, usa Fernet simples.
    Se ambas estiverem configuradas, usa MultiFernet para que dados cifrados com
    a chave antiga (SECRET_KEY) ainda sejam legíveis, enquanto novos dados são
    cifrados com ``ENCRYPTION_KEY``.
    """
    encryption_key_raw: str = getattr(settings, "ENCRYPTION_KEY", "")
    secret_key: str = settings.SECRET_KEY

    legacy_key = _build_fernet_key(secret_key)

    if encryption_key_raw:
        # Aceita tanto valor bruto (≥32 chars) quanto base64 Fernet válido (44 chars)
        primary_key = _build_fernet_key(encryption_key_raw)
        # MultiFernet: cifra com primary_key, decifra tentando ambas em ordem
        return MultiFernet([Fernet(primary_key), Fernet(legacy_key)])

    # Sem chave dedicada: usa derivação de SECRET_KEY (comportamento legado)
    logger.warning(
        "ENCRYPTION_KEY not set — falling back to SECRET_KEY derivation. "
        "Set ENCRYPTION_KEY in your environment or Docker secret for better security."
    )
    return Fernet(legacy_key)


class FieldEncryption:
    """Handles encryption and decryption of sensitive database fields.

    Attributes:
        _fernet: Fernet (or MultiFernet) cipher instance for encrypt/decrypt operations.
    """

    def __init__(self) -> None:
        """Initialize with encryption key from ENCRYPTION_KEY setting (preferred)
        or fall back to a key derived from SECRET_KEY."""
        self._fernet = _make_fernet()

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
        except InvalidToken:
            logger.error("Failed to decrypt field value — token invalid or key mismatch.")
            return ""
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


def reset_encryptor() -> None:
    """Reset the global encryptor singleton (useful for testing key rotation)."""
    global _encryptor
    _encryptor = None


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
