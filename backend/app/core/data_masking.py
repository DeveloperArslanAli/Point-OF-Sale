"""Data masking utilities for PII and sensitive data.

Provides masking functions for:
- Credit/debit card numbers
- Email addresses
- Phone numbers
- Personal names
- General PII in log messages
"""

from __future__ import annotations

import re
from typing import Any


def mask_card_number(card_number: str | None) -> str:
    """Mask a credit/debit card number, showing only last 4 digits.
    
    Args:
        card_number: Full card number (may include spaces/dashes)
        
    Returns:
        Masked card number (e.g., "****-****-****-1234")
        
    Examples:
        >>> mask_card_number("4111111111111111")
        '****-****-****-1111'
        >>> mask_card_number("4111-1111-1111-1111")
        '****-****-****-1111'
        >>> mask_card_number(None)
        '****-****-****-****'
    """
    if not card_number:
        return "****-****-****-****"
    
    # Remove spaces and dashes
    digits = re.sub(r"[\s\-]", "", card_number)
    
    if len(digits) < 4:
        return "****-****-****-****"
    
    last_four = digits[-4:]
    return f"****-****-****-{last_four}"


def mask_email(email: str | None) -> str:
    """Mask an email address, showing partial local part and domain.
    
    Args:
        email: Full email address
        
    Returns:
        Masked email (e.g., "jo***@example.com")
        
    Examples:
        >>> mask_email("john.doe@example.com")
        'jo***@example.com'
        >>> mask_email("a@b.com")
        'a***@b.com'
        >>> mask_email(None)
        '***@***.***'
    """
    if not email or "@" not in email:
        return "***@***.***"
    
    local, domain = email.rsplit("@", 1)
    
    if len(local) <= 2:
        masked_local = local[0] + "***" if local else "***"
    else:
        masked_local = local[:2] + "***"
    
    return f"{masked_local}@{domain}"


def mask_phone(phone: str | None) -> str:
    """Mask a phone number, showing only last 4 digits.
    
    Args:
        phone: Full phone number (any format)
        
    Returns:
        Masked phone (e.g., "***-***-1234")
        
    Examples:
        >>> mask_phone("+1-555-123-4567")
        '***-***-4567'
        >>> mask_phone("5551234567")
        '***-***-4567'
        >>> mask_phone(None)
        '***-***-****'
    """
    if not phone:
        return "***-***-****"
    
    # Extract digits only
    digits = re.sub(r"[^\d]", "", phone)
    
    if len(digits) < 4:
        return "***-***-****"
    
    last_four = digits[-4:]
    return f"***-***-{last_four}"


def mask_name(name: str | None) -> str:
    """Mask a personal name, showing first initial.
    
    Args:
        name: Full name
        
    Returns:
        Masked name (e.g., "J***")
        
    Examples:
        >>> mask_name("John Doe")
        'J*** D***'
        >>> mask_name("Jane")
        'J***'
        >>> mask_name(None)
        '***'
    """
    if not name:
        return "***"
    
    parts = name.split()
    masked_parts = []
    
    for part in parts:
        if part:
            masked_parts.append(part[0] + "***")
    
    return " ".join(masked_parts) if masked_parts else "***"


def mask_ssn(ssn: str | None) -> str:
    """Mask a Social Security Number, showing only last 4 digits.
    
    Args:
        ssn: Full SSN (any format)
        
    Returns:
        Masked SSN (e.g., "***-**-1234")
        
    Examples:
        >>> mask_ssn("123-45-6789")
        '***-**-6789'
        >>> mask_ssn("123456789")
        '***-**-6789'
        >>> mask_ssn(None)
        '***-**-****'
    """
    if not ssn:
        return "***-**-****"
    
    digits = re.sub(r"[^\d]", "", ssn)
    
    if len(digits) < 4:
        return "***-**-****"
    
    last_four = digits[-4:]
    return f"***-**-{last_four}"


# Regex patterns for auto-detection
PATTERNS = {
    "card": re.compile(r"\b(?:\d{4}[\s\-]?){3}\d{4}\b"),
    "email": re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"),
    "phone": re.compile(r"\b(?:\+?1[\s.-]?)?(?:\(?\d{3}\)?[\s.-]?)?\d{3}[\s.-]?\d{4}\b"),
    "ssn": re.compile(r"\b\d{3}[\s.-]?\d{2}[\s.-]?\d{4}\b"),
}


def mask_pii_in_text(text: str) -> str:
    """Auto-detect and mask PII in a text string.
    
    Detects and masks:
    - Credit card numbers
    - Email addresses
    - Phone numbers
    - SSNs
    
    Args:
        text: Text that may contain PII
        
    Returns:
        Text with PII masked
        
    Examples:
        >>> mask_pii_in_text("Card: 4111-1111-1111-1111 Email: john@example.com")
        'Card: ****-****-****-1111 Email: jo***@example.com'
    """
    result = text
    
    # Mask credit cards
    for match in PATTERNS["card"].finditer(text):
        result = result.replace(match.group(), mask_card_number(match.group()))
    
    # Mask emails
    for match in PATTERNS["email"].finditer(text):
        result = result.replace(match.group(), mask_email(match.group()))
    
    # Mask phone numbers
    for match in PATTERNS["phone"].finditer(text):
        result = result.replace(match.group(), mask_phone(match.group()))
    
    # Mask SSNs
    for match in PATTERNS["ssn"].finditer(text):
        result = result.replace(match.group(), mask_ssn(match.group()))
    
    return result


def mask_dict_values(
    data: dict[str, Any],
    sensitive_keys: set[str] | None = None,
) -> dict[str, Any]:
    """Mask sensitive values in a dictionary for logging.
    
    Args:
        data: Dictionary that may contain sensitive values
        sensitive_keys: Set of keys to mask (uses defaults if None)
        
    Returns:
        New dictionary with sensitive values masked
        
    Examples:
        >>> mask_dict_values({"email": "john@example.com", "name": "John"})
        {'email': 'jo***@example.com', 'name': 'John'}
    """
    if sensitive_keys is None:
        sensitive_keys = {
            "password",
            "secret",
            "token",
            "api_key",
            "apikey",
            "auth",
            "authorization",
            "credit_card",
            "card_number",
            "cvv",
            "cvc",
            "ssn",
            "social_security",
        }
    
    email_keys = {"email", "email_address", "user_email"}
    phone_keys = {"phone", "phone_number", "mobile", "telephone"}
    card_keys = {"card_number", "credit_card", "card"}
    
    result = {}
    
    for key, value in data.items():
        key_lower = key.lower()
        
        if isinstance(value, dict):
            result[key] = mask_dict_values(value, sensitive_keys)
        elif isinstance(value, str):
            if key_lower in sensitive_keys:
                result[key] = "***REDACTED***"
            elif key_lower in email_keys:
                result[key] = mask_email(value)
            elif key_lower in phone_keys:
                result[key] = mask_phone(value)
            elif key_lower in card_keys:
                result[key] = mask_card_number(value)
            else:
                result[key] = value
        else:
            result[key] = value
    
    return result


class MaskedValue:
    """Wrapper that masks value in string representation.
    
    Useful for logging sensitive values without exposing them.
    
    Examples:
        >>> masked = MaskedValue("secret123", "***")
        >>> print(f"Password: {masked}")
        Password: ***
        >>> masked.get_value()
        'secret123'
    """
    
    def __init__(self, value: Any, display: str = "***MASKED***") -> None:
        """Initialize masked value.
        
        Args:
            value: The actual value to protect
            display: String to show when converted to string
        """
        self._value = value
        self._display = display
    
    def __str__(self) -> str:
        return self._display
    
    def __repr__(self) -> str:
        return f"MaskedValue({self._display})"
    
    def get_value(self) -> Any:
        """Get the actual unmasked value."""
        return self._value
