from __future__ import annotations

import json
from functools import lru_cache
from typing import ClassVar, Literal

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", ".env.local"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    _DEFAULT_SECRET_SENTINEL: ClassVar[str] = "CHANGE_ME"

    ENV: Literal["dev", "test", "staging", "prod"] = "dev"
    DEBUG: bool = False

    APP_NAME: str = "retail-pos-backend"
    API_V1_PREFIX: str = "/api/v1"

    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///./dev.db"  # Development default; override outside dev/test.
    DATABASE_ECHO: bool | None = None

    # Security
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7
    JWT_ALGORITHM: str = "HS256"
    JWT_SECRET_KEY: str = _DEFAULT_SECRET_SENTINEL
    # Used for field-level encryption (defaults to JWT secret when not set)
    SECRET_KEY: str = _DEFAULT_SECRET_SENTINEL
    JWT_ISSUER: str = "retail-pos"

    # CORS / Hosts
    CORS_ORIGINS: list[str] = []
    CORS_ALLOW_CREDENTIALS: bool = True
    CORS_ALLOW_METHODS: list[str] = ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]
    CORS_ALLOW_HEADERS: list[str] = [
        "Authorization",
        "Content-Type",
        "X-Requested-With",
        "X-Trace-Id",
    ]
    ALLOWED_HOSTS: list[str] = ["*"]

    # Observability (placeholders)
    ENABLE_TRACING: bool = False

    # Inventory / sales behavior
    ENFORCE_STOCK_ON_SALE: bool = False

    # Cache
    REDIS_URL: str = "redis://localhost:6379/0"
    
    # Celery Configuration
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/1"

    # Alerting
    ALERT_COOLDOWN_MINUTES: int = 5
    
    # Email/SMTP Configuration (optional)
    SMTP_HOST: str | None = None
    SMTP_PORT: int = 587
    SMTP_USER: str | None = None
    SMTP_PASSWORD: str | None = None
    SMTP_FROM_EMAIL: str = "noreply@retailpos.local"
    SMTP_FROM_NAME: str = "Retail POS System"
    
    # Payment Provider Configuration
    STRIPE_SECRET_KEY: str | None = None
    STRIPE_PUBLISHABLE_KEY: str | None = None
    STRIPE_WEBHOOK_SECRET: str | None = None
    PAYMENT_CURRENCY: str = "USD"  # Default currency for payments
    
    # Security - IP Allowlisting
    IP_ALLOWLIST: str = ""  # Comma-separated list of allowed IPs/CIDRs for admin endpoints
    
    # Observability - OpenTelemetry
    OTEL_ENABLED: bool = False
    OTEL_SERVICE_NAME: str = "retail-pos-backend"
    OTEL_EXPORTER_OTLP_ENDPOINT: str = "http://localhost:4317"
    OTEL_EXPORTER_OTLP_PROTOCOL: str = "grpc"  # grpc or http/protobuf
    SENTRY_DSN: str | None = None

    @property
    def database_echo(self) -> bool:
        return self.DATABASE_ECHO if self.DATABASE_ECHO is not None else self.DEBUG

    @field_validator("CORS_ORIGINS", "ALLOWED_HOSTS", mode="before")
    @classmethod
    def _split_csv(cls, value: list[str] | str | None) -> list[str]:
        if value is None:
            return []
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                return []
            if stripped.startswith("[") and stripped.endswith("]"):
                try:
                    parsed = json.loads(stripped)
                except json.JSONDecodeError:
                    pass
                else:
                    if isinstance(parsed, list):
                        return [str(item).strip() for item in parsed if str(item).strip()]
            return [item.strip() for item in stripped.split(",") if item.strip()]
        return list(value)

    @model_validator(mode="after")
    def _enforce_secure_defaults(self) -> "Settings":
        if self.ENV in {"staging", "prod"}:
            if not self.CORS_ORIGINS:
                raise ValueError("CORS_ORIGINS must be configured for staging/prod environments")
            if any(host == "*" for host in self.ALLOWED_HOSTS):
                raise ValueError("ALLOWED_HOSTS cannot contain '*' outside dev/test")
            if self.JWT_SECRET_KEY == self._DEFAULT_SECRET_SENTINEL:
                raise ValueError("JWT_SECRET_KEY must be overridden for staging/prod environments")
            if self.SECRET_KEY == self._DEFAULT_SECRET_SENTINEL:
                raise ValueError("SECRET_KEY must be set for staging/prod environments")
            if self.DATABASE_URL.startswith("sqlite+"):
                raise ValueError("DATABASE_URL must point to Postgres in staging/prod environments")
            if "ENFORCE_STOCK_ON_SALE" not in self.model_fields_set:
                object.__setattr__(self, "ENFORCE_STOCK_ON_SALE", True)

        # Backwards compatibility: if SECRET_KEY not provided, reuse JWT secret
        if self.SECRET_KEY == self._DEFAULT_SECRET_SENTINEL and self.JWT_SECRET_KEY != self._DEFAULT_SECRET_SENTINEL:
            object.__setattr__(self, "SECRET_KEY", self.JWT_SECRET_KEY)
        return self


@lru_cache
def get_settings() -> Settings:  # pragma: no cover - trivial
    return Settings()
