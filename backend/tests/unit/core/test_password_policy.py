"""Unit tests for password policy enforcement."""
from __future__ import annotations

import pytest

from app.core.password_policy import (
    PasswordPolicy,
    validate_password,
    COMMON_PASSWORDS,
)


class TestPasswordPolicy:
    """Tests for PasswordPolicy class."""

    def test_valid_password_passes(self):
        """Test that a strong password passes all checks."""
        policy = PasswordPolicy()
        result = policy.validate_sync("SecureP@ss123!")
        assert result.is_valid
        assert len(result.errors) == 0
        assert result.strength_score >= 70

    def test_short_password_fails(self):
        """Test that passwords under minimum length fail."""
        policy = PasswordPolicy(min_length=8)
        result = policy.validate_sync("P@ss1")
        assert not result.is_valid
        assert any("at least 8" in e for e in result.errors)

    def test_missing_uppercase_fails(self):
        """Test that missing uppercase fails when required."""
        policy = PasswordPolicy(require_uppercase=True)
        result = policy.validate_sync("password123!")
        assert not result.is_valid
        assert any("uppercase" in e.lower() for e in result.errors)

    def test_missing_lowercase_fails(self):
        """Test that missing lowercase fails when required."""
        policy = PasswordPolicy(require_lowercase=True)
        result = policy.validate_sync("PASSWORD123!")
        assert not result.is_valid
        assert any("lowercase" in e.lower() for e in result.errors)

    def test_missing_digit_fails(self):
        """Test that missing digit fails when required."""
        policy = PasswordPolicy(require_digit=True)
        result = policy.validate_sync("Password!")
        assert not result.is_valid
        assert any("digit" in e.lower() for e in result.errors)

    def test_missing_special_char_fails(self):
        """Test that missing special character fails when required."""
        policy = PasswordPolicy(require_special=True)
        result = policy.validate_sync("Password123")
        assert not result.is_valid
        assert any("special" in e.lower() for e in result.errors)

    def test_common_password_fails(self):
        """Test that common passwords are rejected."""
        policy = PasswordPolicy(check_common=True)
        result = policy.validate_sync("password")
        assert not result.is_valid
        assert any("common" in e.lower() for e in result.errors)

    def test_common_passwords_list_not_empty(self):
        """Verify common passwords list is populated."""
        assert len(COMMON_PASSWORDS) >= 40
        assert "password" in COMMON_PASSWORDS
        assert "123456" in COMMON_PASSWORDS

    def test_empty_password_fails(self):
        """Test that empty password fails."""
        result = validate_password("")
        assert len(result) > 0

    def test_none_password_fails(self):
        """Test that None password fails."""
        policy = PasswordPolicy()
        result = policy.validate_sync(None)  # type: ignore
        assert not result.is_valid

    def test_strength_score_increases_with_length(self):
        """Test that longer passwords get higher scores."""
        policy = PasswordPolicy()
        short_result = policy.validate_sync("P@ss123!")
        long_result = policy.validate_sync("MyVeryL0ng@ndSecureP@ssword!")
        assert long_result.strength_score > short_result.strength_score

    def test_validate_password_convenience_function(self):
        """Test the convenience function returns errors list."""
        errors = validate_password("weak")
        assert isinstance(errors, list)
        assert len(errors) > 0

    def test_max_length_enforced(self):
        """Test that passwords exceeding max length fail."""
        policy = PasswordPolicy(max_length=50)
        long_password = "A" * 51 + "@1a"
        result = policy.validate_sync(long_password)
        assert not result.is_valid
        assert any("at most" in e for e in result.errors)

    def test_disabled_requirements_pass(self):
        """Test that disabled requirements don't cause failures."""
        policy = PasswordPolicy(
            min_length=4,
            require_uppercase=False,
            require_lowercase=False,
            require_digit=False,
            require_special=False,
            check_common=False,
        )
        result = policy.validate_sync("weak")
        assert result.is_valid
