"""Unit tests for data masking utilities."""

from __future__ import annotations

import pytest

from app.core.data_masking import (
    MaskedValue,
    mask_card_number,
    mask_dict_values,
    mask_email,
    mask_name,
    mask_phone,
    mask_pii_in_text,
    mask_ssn,
)


class TestMaskCardNumber:
    """Tests for mask_card_number function."""

    def test_mask_full_card_number(self) -> None:
        """Should mask all but last 4 digits."""
        result = mask_card_number("4111111111111111")
        assert result == "****-****-****-1111"

    def test_mask_card_with_dashes(self) -> None:
        """Should handle card numbers with dashes."""
        result = mask_card_number("4111-1111-1111-1111")
        assert result == "****-****-****-1111"

    def test_mask_card_with_spaces(self) -> None:
        """Should handle card numbers with spaces."""
        result = mask_card_number("4111 1111 1111 1111")
        assert result == "****-****-****-1111"

    def test_mask_none_card(self) -> None:
        """Should handle None input."""
        result = mask_card_number(None)
        assert result == "****-****-****-****"

    def test_mask_short_card(self) -> None:
        """Should handle short numbers."""
        result = mask_card_number("123")
        assert result == "****-****-****-****"


class TestMaskEmail:
    """Tests for mask_email function."""

    def test_mask_standard_email(self) -> None:
        """Should mask email showing first 2 chars of local part."""
        result = mask_email("john.doe@example.com")
        assert result == "jo***@example.com"

    def test_mask_short_email(self) -> None:
        """Should handle short local part."""
        result = mask_email("a@b.com")
        assert result == "a***@b.com"

    def test_mask_none_email(self) -> None:
        """Should handle None input."""
        result = mask_email(None)
        assert result == "***@***.***"

    def test_mask_invalid_email(self) -> None:
        """Should handle invalid email without @."""
        result = mask_email("notanemail")
        assert result == "***@***.***"


class TestMaskPhone:
    """Tests for mask_phone function."""

    def test_mask_standard_phone(self) -> None:
        """Should show only last 4 digits."""
        result = mask_phone("+1-555-123-4567")
        assert result == "***-***-4567"

    def test_mask_digits_only(self) -> None:
        """Should handle digits-only phone."""
        result = mask_phone("5551234567")
        assert result == "***-***-4567"

    def test_mask_none_phone(self) -> None:
        """Should handle None input."""
        result = mask_phone(None)
        assert result == "***-***-****"


class TestMaskName:
    """Tests for mask_name function."""

    def test_mask_full_name(self) -> None:
        """Should show first initial of each part."""
        result = mask_name("John Doe")
        assert result == "J*** D***"

    def test_mask_single_name(self) -> None:
        """Should handle single name."""
        result = mask_name("Jane")
        assert result == "J***"

    def test_mask_none_name(self) -> None:
        """Should handle None input."""
        result = mask_name(None)
        assert result == "***"


class TestMaskSsn:
    """Tests for mask_ssn function."""

    def test_mask_formatted_ssn(self) -> None:
        """Should show only last 4 digits."""
        result = mask_ssn("123-45-6789")
        assert result == "***-**-6789"

    def test_mask_unformatted_ssn(self) -> None:
        """Should handle unformatted SSN."""
        result = mask_ssn("123456789")
        assert result == "***-**-6789"

    def test_mask_none_ssn(self) -> None:
        """Should handle None input."""
        result = mask_ssn(None)
        assert result == "***-**-****"


class TestMaskPiiInText:
    """Tests for mask_pii_in_text function."""

    def test_mask_card_in_text(self) -> None:
        """Should detect and mask card numbers in text."""
        result = mask_pii_in_text("Card: 4111-1111-1111-1111")
        assert "****-****-****-1111" in result

    def test_mask_email_in_text(self) -> None:
        """Should detect and mask emails in text."""
        result = mask_pii_in_text("Email: john@example.com")
        assert "jo***@example.com" in result


class TestMaskDictValues:
    """Tests for mask_dict_values function."""

    def test_mask_password(self) -> None:
        """Should mask password field."""
        result = mask_dict_values({"password": "secret123", "name": "John"})
        assert result["password"] == "***REDACTED***"
        assert result["name"] == "John"

    def test_mask_email_field(self) -> None:
        """Should mask email field."""
        result = mask_dict_values({"email": "john@example.com"})
        assert result["email"] == "jo***@example.com"

    def test_mask_nested_dict(self) -> None:
        """Should mask nested dictionaries."""
        result = mask_dict_values({
            "user": {"password": "secret", "email": "a@b.com"}
        })
        assert result["user"]["password"] == "***REDACTED***"


class TestMaskedValue:
    """Tests for MaskedValue class."""

    def test_string_representation(self) -> None:
        """Should show masked value in string."""
        masked = MaskedValue("secret123", "***")
        assert str(masked) == "***"

    def test_get_value(self) -> None:
        """Should return actual value with get_value."""
        masked = MaskedValue("secret123", "***")
        assert masked.get_value() == "secret123"

    def test_repr(self) -> None:
        """Should show MaskedValue in repr."""
        masked = MaskedValue("secret123", "***")
        assert repr(masked) == "MaskedValue(***)"
