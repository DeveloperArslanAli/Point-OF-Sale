from __future__ import annotations

import logging
import re
import sys
from typing import Any
from uuid import uuid4

import structlog
from structlog.contextvars import bind_contextvars, clear_contextvars


# PII field patterns to mask in logs
PII_FIELDS = frozenset({
    "password", "password_hash", "new_password", "old_password",
    "secret", "secret_key", "api_key", "token", "access_token", "refresh_token",
    "card_number", "credit_card", "cvv", "cvc", "ssn", "social_security",
    "phone", "phone_number", "mobile", "cell",
    "email", "email_address",
    "address", "street_address", "billing_address",
    "first_name", "last_name", "full_name", "name",
})

# Email regex pattern
EMAIL_PATTERN = re.compile(r"([a-zA-Z0-9._%+-]+)@([a-zA-Z0-9.-]+\.[a-zA-Z]{2,})")

# Phone pattern (various formats)
PHONE_PATTERN = re.compile(r"\b(\+?1?[-.\s]?)?\(?([0-9]{3})\)?[-.\s]?([0-9]{3})[-.\s]?([0-9]{4})\b")


def _mask_value(value: Any, field_name: str) -> Any:
    """Mask a single value based on field name."""
    if value is None or value == "":
        return value
    
    field_lower = field_name.lower()
    
    # Full mask for sensitive tokens/passwords
    if any(term in field_lower for term in ("password", "secret", "token", "key", "cvv", "cvc")):
        return "***REDACTED***"
    
    # SSN mask
    if "ssn" in field_lower or "social" in field_lower:
        return "***-**-****"
    
    if not isinstance(value, str):
        return value
    
    # Partial mask for identifiable info
    if "email" in field_lower:
        match = EMAIL_PATTERN.match(value)
        if match:
            local = match.group(1)
            domain = match.group(2)
            if len(local) <= 2:
                masked_local = "*" * len(local)
            else:
                masked_local = local[0] + "*" * (len(local) - 2) + local[-1]
            return f"{masked_local}@{domain}"
        return value
    
    if "phone" in field_lower or "mobile" in field_lower or "cell" in field_lower:
        if len(value) >= 4:
            return "*" * (len(value) - 4) + value[-4:]
        return "****"
    
    if "name" in field_lower:
        if len(value) <= 1:
            return "*"
        return value[0] + "*" * (len(value) - 1)
    
    if "address" in field_lower:
        # Show only first word for addresses
        parts = value.split()
        if len(parts) > 1:
            return parts[0] + " ***"
        return value
    
    return value


def _mask_pii_in_dict(data: dict[str, Any]) -> dict[str, Any]:
    """Recursively mask PII fields in a dictionary."""
    result = {}
    for key, value in data.items():
        key_lower = key.lower()
        
        # Check if this field should be masked
        should_mask = any(pii_field in key_lower for pii_field in PII_FIELDS)
        
        if should_mask:
            result[key] = _mask_value(value, key)
        elif isinstance(value, dict):
            result[key] = _mask_pii_in_dict(value)
        elif isinstance(value, list):
            result[key] = [
                _mask_pii_in_dict(item) if isinstance(item, dict) else item
                for item in value
            ]
        else:
            result[key] = value
    
    return result


def pii_masking_processor(
    logger: Any,
    method_name: str,
    event_dict: dict[str, Any],
) -> dict[str, Any]:
    """Structlog processor that masks PII fields in log events."""
    return _mask_pii_in_dict(event_dict)


def configure_logging() -> None:  # pragma: no cover (side-effect)
    timestamper = structlog.processors.TimeStamper(fmt="iso")

    shared_processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        timestamper,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        pii_masking_processor,  # Add PII masking before rendering
    ]

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        cache_logger_on_first_use=True,
    )

    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=logging.INFO,
    )


def bind_trace_id(trace_id: str | None = None) -> str:
    """Bind a trace ID into the structlog context, generating one if needed."""
    value = trace_id or str(uuid4())
    bind_contextvars(trace_id=value)
    return value


def reset_context() -> None:
    """Clear any request-scoped context variables."""
    clear_contextvars()
