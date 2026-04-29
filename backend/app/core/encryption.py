"""
Field-level encryption utilities for PCI/GDPR compliance.

Provides Fernet-based encryption for sensitive PII fields like:
- Card last four digits
- Customer phone numbers
- Customer email addresses
- Customer addresses

Usage:
    from app.core.encryption import encrypt_pii, decrypt_pii

    # Encrypt before storing
    encrypted = encrypt_pii("4111111111111111")

    # Decrypt when reading
    original = decrypt_pii(encrypted)
"""

from __future__ import annotations

import base64
import hashlib
import os
from functools import lru_cache
from typing import TYPE_CHECKING

from cryptography.fernet import Fernet, InvalidToken

from app.core.settings import get_settings

if TYPE_CHECKING:
    pass


class EncryptionError(Exception):
    """Raised when encryption/decryption fails."""
    pass


@lru_cache(maxsize=1)
def _get_fernet() -> Fernet:
    """
    Get Fernet instance with encryption key from settings.
    
    The key should be a 32-byte URL-safe base64-encoded string.
    If not configured, generates a key from SECRET_KEY.
    """
    settings = get_settings()
    
    # Try to use dedicated encryption key first
    encryption_key = getattr(settings, "ENCRYPTION_KEY", None)
    
    if encryption_key:
        # Validate it's a proper Fernet key
        try:
            return Fernet(encryption_key.encode() if isinstance(encryption_key, str) else encryption_key)
        except Exception:
            pass
    
    # Fall back to deriving from SECRET_KEY
    secret_key = settings.SECRET_KEY
    if not secret_key:
        raise EncryptionError("No SECRET_KEY configured for encryption")
    
    # Derive a 32-byte key from SECRET_KEY using SHA256
    derived = hashlib.sha256(secret_key.encode()).digest()
    fernet_key = base64.urlsafe_b64encode(derived)
    
    return Fernet(fernet_key)


def encrypt_pii(plaintext: str | None) -> str | None:
    """
    Encrypt a PII field value.
    
    Args:
        plaintext: The sensitive data to encrypt
        
    Returns:
        Base64-encoded encrypted string, or None if input is None
        
    Raises:
        EncryptionError: If encryption fails
    """
    if plaintext is None:
        return None
    
    if not plaintext:
        return ""
    
    try:
        fernet = _get_fernet()
        encrypted = fernet.encrypt(plaintext.encode("utf-8"))
        return encrypted.decode("utf-8")
    except Exception as e:
        raise EncryptionError(f"Failed to encrypt PII: {e}") from e


def decrypt_pii(ciphertext: str | None) -> str | None:
    """
    Decrypt a PII field value.
    
    Args:
        ciphertext: The encrypted data to decrypt
        
    Returns:
        Decrypted plaintext string, or None if input is None
        
    Raises:
        EncryptionError: If decryption fails (invalid key or corrupted data)
    """
    if ciphertext is None:
        return None
    
    if not ciphertext:
        return ""
    
    try:
        fernet = _get_fernet()
        decrypted = fernet.decrypt(ciphertext.encode("utf-8"))
        return decrypted.decode("utf-8")
    except InvalidToken:
        raise EncryptionError("Invalid encryption token - data may be corrupted or key changed")
    except Exception as e:
        raise EncryptionError(f"Failed to decrypt PII: {e}") from e


def mask_pii(value: str | None, visible_chars: int = 4, mask_char: str = "*") -> str:
    """
    Mask a PII value for display, showing only last N characters.
    
    Args:
        value: The sensitive value to mask
        visible_chars: Number of characters to show at the end
        mask_char: Character to use for masking
        
    Returns:
        Masked string like "****1234"
    """
    if not value:
        return ""
    
    if len(value) <= visible_chars:
        return mask_char * len(value)
    
    masked_length = len(value) - visible_chars
    return mask_char * masked_length + value[-visible_chars:]


def hash_for_lookup(value: str) -> str:
    """
    Create a deterministic hash of a value for lookup purposes.
    
    Use this when you need to search encrypted fields without decrypting.
    Store both the encrypted value and the hash, then search by hash.
    
    Args:
        value: The value to hash
        
    Returns:
        SHA256 hash as hex string
    """
    settings = get_settings()
    # Add salt from secret key for extra security
    salted = f"{settings.SECRET_KEY}:{value}"
    return hashlib.sha256(salted.encode()).hexdigest()


def generate_encryption_key() -> str:
    """
    Generate a new Fernet encryption key.
    
    Use this to create a key for the ENCRYPTION_KEY setting.
    
    Returns:
        URL-safe base64-encoded 32-byte key
    """
    return Fernet.generate_key().decode("utf-8")


class EncryptedField:
    """
    Descriptor for transparent encryption/decryption of model fields.
    
    Usage in SQLAlchemy models:
        class CustomerModel(Base):
            _phone_encrypted = Column(String(500))
            phone = EncryptedField("_phone_encrypted")
    """
    
    def __init__(self, encrypted_attr: str):
        self.encrypted_attr = encrypted_attr
    
    def __get__(self, obj, objtype=None) -> str | None:
        if obj is None:
            return None
        encrypted = getattr(obj, self.encrypted_attr)
        try:
            return decrypt_pii(encrypted)
        except EncryptionError:
            # Return masked value if decryption fails
            return mask_pii(encrypted, 4)
    
    def __set__(self, obj, value: str | None) -> None:
        encrypted = encrypt_pii(value)
        setattr(obj, self.encrypted_attr, encrypted)
