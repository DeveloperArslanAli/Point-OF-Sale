"""
SQLAlchemy custom type for transparent field-level encryption.

Provides automatic encryption/decryption for PCI/GDPR sensitive fields
like phone numbers, email addresses, and card data.

Usage:
    from app.infrastructure.db.types.encrypted_type import EncryptedString
    
    class CustomerModel(Base):
        email_encrypted: Mapped[str] = mapped_column(EncryptedString(255))
"""
from __future__ import annotations

from typing import Any

from sqlalchemy import String, TypeDecorator

from app.core.encryption import decrypt_pii, encrypt_pii, hash_for_lookup


class EncryptedString(TypeDecorator):
    """
    Encrypted string type for SQLAlchemy.
    
    Automatically encrypts on write and decrypts on read.
    Stored data is longer than input due to Fernet encryption overhead.
    """
    
    impl = String
    cache_ok = True
    
    def __init__(self, length: int = 500, **kwargs):
        """
        Initialize encrypted string type.
        
        Args:
            length: Maximum length of the encrypted value (should be ~3x plaintext)
        """
        # Encrypted strings are longer - allocate ~3x space
        super().__init__(length=max(length, 500), **kwargs)
    
    def process_bind_param(self, value: str | None, dialect) -> str | None:
        """Encrypt value before storing in database."""
        if value is None:
            return None
        if not value:
            return ""
        return encrypt_pii(value)
    
    def process_result_value(self, value: str | None, dialect) -> str | None:
        """Decrypt value when reading from database."""
        if value is None:
            return None
        if not value:
            return ""
        try:
            return decrypt_pii(value)
        except Exception:
            # Return as-is if decryption fails (might be legacy unencrypted data)
            return value


class EncryptedEmail(EncryptedString):
    """
    Encrypted email type with optional hash column for lookups.
    
    For searchable encrypted emails, also store a hash:
        email_encrypted = Column(EncryptedEmail())
        email_hash = Column(String(64), index=True)
    """
    cache_ok = True
    
    def __init__(self, **kwargs):
        super().__init__(length=500, **kwargs)


class EncryptedPhone(EncryptedString):
    """
    Encrypted phone number type.
    """
    
    def __init__(self, **kwargs):
        super().__init__(length=300, **kwargs)


class EncryptedCardLast4(TypeDecorator):
    """
    Encrypted card last 4 digits.
    
    For PCI-DSS compliance, even partial card numbers should be encrypted.
    """
    
    impl = String
    cache_ok = True
    
    def __init__(self, **kwargs):
        super().__init__(length=200, **kwargs)
    
    def process_bind_param(self, value: str | None, dialect) -> str | None:
        if value is None:
            return None
        if not value:
            return ""
        return encrypt_pii(value)
    
    def process_result_value(self, value: str | None, dialect) -> str | None:
        if value is None:
            return None
        if not value:
            return ""
        try:
            return decrypt_pii(value)
        except Exception:
            return value


def generate_lookup_hash(value: str) -> str:
    """
    Generate a deterministic hash for encrypted field lookups.
    
    Use this when you need to search by encrypted values:
        email_hash = generate_lookup_hash(email)
        await repo.find_by_email_hash(email_hash)
    """
    return hash_for_lookup(value)
