# Pydantic Config Guidelines

We are on Pydantic v2. Use these patterns to avoid deprecation warnings and keep serialization consistent:

- Prefer `model_config = ConfigDict(...)` instead of class `Config`.
- Replace `json_encoders` with `field_serializer` on the specific fields that need stringification (e.g., `Decimal`, `datetime`).
- For ORM responses, set `model_config = ConfigDict(from_attributes=True)`.
- For custom serialization of optionals, ensure serializers handle `None` safely.
- When adding new models, avoid `datetime.utcnow`; prefer `datetime.now(UTC)`.

If you touch existing models that still use legacy patterns, migrate them using the above approach and rerun `pytest` to confirm warnings stay clear.
