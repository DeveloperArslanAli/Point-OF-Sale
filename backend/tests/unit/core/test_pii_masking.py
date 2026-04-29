"""Unit tests for PII masking in logging."""
from __future__ import annotations

import pytest

from app.core.logging import (
    _mask_value,
    _mask_pii_in_dict,
    pii_masking_processor,
)


class TestPIIMasking:
    """Tests for PII masking functions."""

    def test_mask_password_field(self):
        """Test password fields are fully redacted."""
        result = _mask_value("mysecretpass", "password")
        assert result == "***REDACTED***"

    def test_mask_secret_key_field(self):
        """Test secret key fields are fully redacted."""
        result = _mask_value("abc123xyz", "secret_key")
        assert result == "***REDACTED***"

    def test_mask_token_field(self):
        """Test token fields are fully redacted."""
        result = _mask_value("jwt.token.here", "access_token")
        assert result == "***REDACTED***"

    def test_mask_email_field(self):
        """Test email fields are partially masked."""
        result = _mask_value("john.doe@example.com", "email")
        assert "@example.com" in result
        assert "*" in result
        # First and last char of local part visible
        assert result[0] == "j"

    def test_mask_short_email(self):
        """Test short email local parts are masked."""
        result = _mask_value("ab@example.com", "email")
        assert "@example.com" in result
        assert "*" in result

    def test_mask_phone_field(self):
        """Test phone fields show only last 4 digits."""
        result = _mask_value("1234567890", "phone")
        assert result.endswith("7890")
        assert result.startswith("*")

    def test_mask_name_field(self):
        """Test name fields show only first letter."""
        result = _mask_value("John", "first_name")
        assert result == "J***"

    def test_mask_ssn_field(self):
        """Test SSN fields are fully masked."""
        result = _mask_value("123-45-6789", "ssn")
        assert result == "***-**-****"

    def test_mask_address_field(self):
        """Test address fields show only first word."""
        result = _mask_value("123 Main Street", "address")
        assert result == "123 ***"

    def test_none_value_unchanged(self):
        """Test None values are not changed."""
        result = _mask_value(None, "email")
        assert result is None

    def test_empty_string_unchanged(self):
        """Test empty strings are not changed."""
        result = _mask_value("", "email")
        assert result == ""

    def test_mask_pii_in_dict_recursive(self):
        """Test dictionary masking works recursively."""
        data = {
            "user": {
                "email": "test@example.com",
                "password": "secret123",
            },
            "safe_field": "not masked",
        }
        
        result = _mask_pii_in_dict(data)
        
        assert result["user"]["password"] == "***REDACTED***"
        assert "*" in result["user"]["email"]
        assert result["safe_field"] == "not masked"

    def test_mask_pii_in_list(self):
        """Test dictionary masking works with lists."""
        data = {
            "users": [
                {"email": "a@example.com"},
                {"email": "b@example.com"},
            ]
        }
        
        result = _mask_pii_in_dict(data)
        
        assert "*" in result["users"][0]["email"]
        assert "*" in result["users"][1]["email"]

    def test_pii_masking_processor(self):
        """Test the structlog processor function."""
        event_dict = {
            "event": "user_created",
            "email": "user@example.com",
            "password": "supersecret",
        }
        
        result = pii_masking_processor(None, "info", event_dict)
        
        assert result["password"] == "***REDACTED***"
        assert "*" in result["email"]
        assert result["event"] == "user_created"

    def test_non_string_values_handled(self):
        """Test non-string values are handled gracefully."""
        result = _mask_value(12345, "phone_number")
        assert result == 12345  # Numbers not modified

    def test_case_insensitive_field_matching(self):
        """Test field name matching is case-insensitive."""
        data = {
            "EMAIL": "test@example.com",
            "Password": "secret",
        }
        
        result = _mask_pii_in_dict(data)
        
        assert "*" in result["EMAIL"]
        assert result["Password"] == "***REDACTED***"
