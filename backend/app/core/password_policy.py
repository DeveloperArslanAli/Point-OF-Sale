"""Password policy enforcement for security compliance.

This module provides password strength validation, common password detection,
and optional breach checking via the Have I Been Pwned API.

Usage:
    from app.core.password_policy import PasswordPolicy, validate_password
    
    # Simple validation
    errors = validate_password("MyP@ssw0rd123")
    if errors:
        raise ValidationError("Password policy violation", details={"errors": errors})
    
    # Full policy check
    policy = PasswordPolicy()
    result = await policy.check("MyP@ssw0rd123", check_breach=True)
    if not result.is_valid:
        print(result.errors)
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from typing import ClassVar

import httpx
import structlog

from app.core.settings import get_settings

logger = structlog.get_logger()


# Common passwords to reject (top 100 most common)
COMMON_PASSWORDS: frozenset[str] = frozenset({
    "password", "123456", "12345678", "qwerty", "abc123",
    "monkey", "1234567", "letmein", "trustno1", "dragon",
    "baseball", "iloveyou", "master", "sunshine", "ashley",
    "bailey", "shadow", "123123", "654321", "superman",
    "qazwsx", "michael", "football", "password1", "password123",
    "princess", "login", "welcome", "solo", "abc",
    "admin", "passw0rd", "hello", "charlie", "donald",
    "p@ssword", "p@ssw0rd", "pass123", "pass1234", "changeme",
    "letmein123", "welcome1", "welcome123", "admin123", "root",
    "toor", "password12", "password1234", "123456789", "12345",
})


@dataclass
class PasswordCheckResult:
    """Result of password policy validation."""
    is_valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    strength_score: int = 0  # 0-100
    breach_count: int | None = None  # Number of times seen in breaches


class PasswordPolicy:
    """Password policy enforcement with configurable rules.
    
    Default policy:
    - Minimum 8 characters
    - At least one uppercase letter
    - At least one lowercase letter
    - At least one digit
    - At least one special character
    - Not in common password list
    - Optionally checks Have I Been Pwned API
    """
    
    DEFAULT_MIN_LENGTH: ClassVar[int] = 8
    DEFAULT_MAX_LENGTH: ClassVar[int] = 128
    HIBP_API_URL: ClassVar[str] = "https://api.pwnedpasswords.com/range/"
    
    def __init__(
        self,
        *,
        min_length: int = DEFAULT_MIN_LENGTH,
        max_length: int = DEFAULT_MAX_LENGTH,
        require_uppercase: bool = True,
        require_lowercase: bool = True,
        require_digit: bool = True,
        require_special: bool = True,
        check_common: bool = True,
    ) -> None:
        self.min_length = min_length
        self.max_length = max_length
        self.require_uppercase = require_uppercase
        self.require_lowercase = require_lowercase
        self.require_digit = require_digit
        self.require_special = require_special
        self.check_common = check_common

    def validate_sync(self, password: str) -> PasswordCheckResult:
        """Synchronously validate password against policy rules."""
        errors: list[str] = []
        warnings: list[str] = []
        strength_score = 0
        
        if not password:
            return PasswordCheckResult(
                is_valid=False,
                errors=["Password is required"],
                strength_score=0,
            )

        # Length checks
        if len(password) < self.min_length:
            errors.append(f"Password must be at least {self.min_length} characters")
        else:
            strength_score += 20

        if len(password) > self.max_length:
            errors.append(f"Password must be at most {self.max_length} characters")

        # Character class checks
        has_upper = bool(re.search(r"[A-Z]", password))
        has_lower = bool(re.search(r"[a-z]", password))
        has_digit = bool(re.search(r"\d", password))
        has_special = bool(re.search(r"[!@#$%^&*(),.?\":{}|<>_\-+=\[\]\\;'/`~]", password))

        if self.require_uppercase and not has_upper:
            errors.append("Password must contain at least one uppercase letter")
        elif has_upper:
            strength_score += 15

        if self.require_lowercase and not has_lower:
            errors.append("Password must contain at least one lowercase letter")
        elif has_lower:
            strength_score += 15

        if self.require_digit and not has_digit:
            errors.append("Password must contain at least one digit")
        elif has_digit:
            strength_score += 15

        if self.require_special and not has_special:
            errors.append("Password must contain at least one special character")
        elif has_special:
            strength_score += 15

        # Common password check
        if self.check_common and password.lower() in COMMON_PASSWORDS:
            errors.append("Password is too common and easily guessable")
        
        # Bonus points for length
        if len(password) >= 12:
            strength_score += 10
        if len(password) >= 16:
            strength_score += 10

        return PasswordCheckResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            strength_score=min(100, strength_score),
        )

    async def check_breach(self, password: str) -> tuple[bool, int]:
        """Check if password has been seen in data breaches via HIBP API.
        
        Uses k-anonymity model - only sends first 5 chars of SHA1 hash.
        
        Returns:
            Tuple of (is_breached, breach_count)
        """
        settings = get_settings()
        
        # Skip in test environment
        if settings.ENV == "test":
            return False, 0

        try:
            # Hash the password
            sha1_hash = hashlib.sha1(password.encode("utf-8")).hexdigest().upper()
            prefix = sha1_hash[:5]
            suffix = sha1_hash[5:]

            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(
                    f"{self.HIBP_API_URL}{prefix}",
                    headers={"User-Agent": "RetailPOS-Security-Check"},
                )
                response.raise_for_status()

            # Parse response - format: HASH_SUFFIX:COUNT
            for line in response.text.splitlines():
                parts = line.split(":")
                if len(parts) == 2 and parts[0] == suffix:
                    count = int(parts[1])
                    logger.warning(
                        "password_breach_detected",
                        breach_count=count,
                    )
                    return True, count

            return False, 0

        except Exception as e:
            logger.warning(
                "hibp_check_failed",
                error=str(e),
            )
            # Fail open - don't block registration if API is down
            return False, 0

    async def check(
        self,
        password: str,
        *,
        check_breach: bool = False,
    ) -> PasswordCheckResult:
        """Full password validation including optional breach check.
        
        Args:
            password: The password to validate
            check_breach: Whether to check Have I Been Pwned API
            
        Returns:
            PasswordCheckResult with validation details
        """
        result = self.validate_sync(password)

        if check_breach and result.is_valid:
            is_breached, breach_count = await self.check_breach(password)
            result.breach_count = breach_count
            if is_breached:
                result.warnings.append(
                    f"This password has appeared in {breach_count:,} data breaches. "
                    "Consider using a different password."
                )
                # Don't fail validation, just warn
                # result.is_valid = False  # Uncomment to enforce

        return result


# Global policy instance with default settings
_default_policy: PasswordPolicy | None = None


def get_password_policy() -> PasswordPolicy:
    """Get the default password policy instance."""
    global _default_policy
    if _default_policy is None:
        _default_policy = PasswordPolicy()
    return _default_policy


def validate_password(password: str) -> list[str]:
    """Synchronously validate password and return list of errors.
    
    Convenience function for simple validation.
    
    Args:
        password: The password to validate
        
    Returns:
        List of error messages (empty if valid)
    """
    policy = get_password_policy()
    result = policy.validate_sync(password)
    return result.errors
