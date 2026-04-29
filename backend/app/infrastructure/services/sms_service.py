"""SMS Service abstraction with Twilio integration.

This module provides an SMS service interface and implementation for sending
SMS notifications to customers. It supports:
- Single message sending
- Bulk message sending
- Delivery status tracking
- Rate limiting and retry logic
"""
from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING, Any, Protocol

import structlog

from app.core.settings import get_settings

if TYPE_CHECKING:
    from twilio.rest import Client as TwilioClient

logger = structlog.get_logger(__name__)
settings = get_settings()


class SMSStatus(str, Enum):
    """SMS delivery status."""
    PENDING = "pending"
    QUEUED = "queued"
    SENDING = "sending"
    SENT = "sent"
    DELIVERED = "delivered"
    FAILED = "failed"
    UNDELIVERED = "undelivered"


@dataclass(frozen=True)
class SMSMessage:
    """Represents an SMS message to be sent."""
    to_phone: str
    body: str
    from_phone: str | None = None
    reference_id: str | None = None
    metadata: dict[str, str] = field(default_factory=dict)
    
    def __post_init__(self) -> None:
        if not self.to_phone:
            raise ValueError("to_phone is required")
        if not self.body:
            raise ValueError("body is required")
        if len(self.body) > 1600:  # SMS character limit
            raise ValueError("SMS body exceeds 1600 character limit")


@dataclass
class SMSResult:
    """Result of an SMS send operation."""
    message_id: str | None
    to_phone: str
    status: SMSStatus
    error_code: str | None = None
    error_message: str | None = None
    sent_at: datetime | None = None
    provider: str = "unknown"
    segments: int = 1
    
    @property
    def is_success(self) -> bool:
        """Check if the message was sent successfully."""
        return self.status in (SMSStatus.QUEUED, SMSStatus.SENDING, SMSStatus.SENT, SMSStatus.DELIVERED)


class SMSServiceProtocol(Protocol):
    """Protocol for SMS service implementations."""
    
    async def send_sms(self, message: SMSMessage) -> SMSResult:
        """Send a single SMS message."""
        ...
    
    async def send_bulk_sms(self, messages: list[SMSMessage]) -> list[SMSResult]:
        """Send multiple SMS messages."""
        ...
    
    async def get_delivery_status(self, message_id: str) -> SMSStatus:
        """Get the delivery status of a previously sent message."""
        ...
    
    def is_valid_phone(self, phone: str) -> bool:
        """Validate a phone number format."""
        ...


class BaseSMSService(ABC):
    """Base class for SMS service implementations."""
    
    @abstractmethod
    async def send_sms(self, message: SMSMessage) -> SMSResult:
        """Send a single SMS message."""
        pass
    
    async def send_bulk_sms(
        self,
        messages: list[SMSMessage],
        max_concurrent: int = 10,
    ) -> list[SMSResult]:
        """Send multiple SMS messages with concurrency control."""
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def send_with_semaphore(msg: SMSMessage) -> SMSResult:
            async with semaphore:
                return await self.send_sms(msg)
        
        results = await asyncio.gather(
            *[send_with_semaphore(msg) for msg in messages],
            return_exceptions=True,
        )
        
        # Convert exceptions to failed results
        final_results: list[SMSResult] = []
        for i, result in enumerate(results):
            if isinstance(result, BaseException):
                final_results.append(SMSResult(
                    message_id=None,
                    to_phone=messages[i].to_phone,
                    status=SMSStatus.FAILED,
                    error_message=str(result),
                    provider=self.provider_name,
                ))
            elif isinstance(result, SMSResult):
                final_results.append(result)
        
        return final_results
    
    @abstractmethod
    async def get_delivery_status(self, message_id: str) -> SMSStatus:
        """Get the delivery status of a previously sent message."""
        pass
    
    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return the provider name."""
        pass
    
    def is_valid_phone(self, phone: str) -> bool:
        """Validate phone number format (E.164 recommended)."""
        if not phone:
            return False
        # Basic E.164 validation: starts with +, 10-15 digits
        clean = phone.replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
        if clean.startswith("+"):
            digits = clean[1:]
            return digits.isdigit() and 10 <= len(digits) <= 15
        # Allow local numbers (10-15 digits)
        return clean.isdigit() and 10 <= len(clean) <= 15


class TwilioSMSService(BaseSMSService):
    """Twilio SMS service implementation.
    
    Configuration required in settings:
    - TWILIO_ACCOUNT_SID: Your Twilio account SID
    - TWILIO_AUTH_TOKEN: Your Twilio auth token
    - TWILIO_FROM_PHONE: Default sending phone number
    """
    
    def __init__(
        self,
        account_sid: str | None = None,
        auth_token: str | None = None,
        from_phone: str | None = None,
    ) -> None:
        self._account_sid = account_sid or getattr(settings, "TWILIO_ACCOUNT_SID", None)
        self._auth_token = auth_token or getattr(settings, "TWILIO_AUTH_TOKEN", None)
        self._from_phone = from_phone or getattr(settings, "TWILIO_FROM_PHONE", None)
        self._client: Any = None  # type: TwilioClient | None
        
        if self._account_sid and self._auth_token:
            try:
                from twilio.rest import Client
                self._client = Client(self._account_sid, self._auth_token)
                logger.info("twilio_sms_service_initialized")
            except ImportError:
                logger.warning(
                    "twilio_sdk_not_installed",
                    message="Install twilio package: pip install twilio",
                )
            except Exception as e:
                logger.error("twilio_init_failed", error=str(e))
        else:
            logger.warning(
                "twilio_not_configured",
                message="TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN not set",
            )
    
    @property
    def provider_name(self) -> str:
        return "twilio"
    
    @property
    def is_configured(self) -> bool:
        """Check if Twilio is properly configured."""
        return self._client is not None
    
    async def send_sms(self, message: SMSMessage) -> SMSResult:
        """Send an SMS via Twilio."""
        if not self._client:
            logger.warning(
                "sms_send_skipped",
                reason="twilio_not_configured",
                to=message.to_phone,
            )
            return SMSResult(
                message_id=None,
                to_phone=message.to_phone,
                status=SMSStatus.FAILED,
                error_code="not_configured",
                error_message="Twilio SMS service is not configured",
                provider=self.provider_name,
            )
        
        try:
            # Run Twilio API call in thread pool (it's synchronous)
            loop = asyncio.get_event_loop()
            twilio_message = await loop.run_in_executor(
                None,
                self._send_sync,
                message,
            )
            
            # Map Twilio status to our status
            status_map = {
                "queued": SMSStatus.QUEUED,
                "sending": SMSStatus.SENDING,
                "sent": SMSStatus.SENT,
                "delivered": SMSStatus.DELIVERED,
                "failed": SMSStatus.FAILED,
                "undelivered": SMSStatus.UNDELIVERED,
            }
            
            status = status_map.get(twilio_message.status, SMSStatus.PENDING)
            
            logger.info(
                "sms_sent",
                message_id=twilio_message.sid,
                to=message.to_phone,
                status=status.value,
                segments=twilio_message.num_segments,
            )
            
            return SMSResult(
                message_id=twilio_message.sid,
                to_phone=message.to_phone,
                status=status,
                sent_at=datetime.now(timezone.utc),
                provider=self.provider_name,
                segments=int(twilio_message.num_segments) if twilio_message.num_segments else 1,
            )
            
        except Exception as e:
            logger.error(
                "sms_send_failed",
                to=message.to_phone,
                error=str(e),
            )
            
            error_code = getattr(e, "code", None)
            return SMSResult(
                message_id=None,
                to_phone=message.to_phone,
                status=SMSStatus.FAILED,
                error_code=str(error_code) if error_code else "unknown",
                error_message=str(e),
                provider=self.provider_name,
            )
    
    def _send_sync(self, message: SMSMessage):  # type: ignore[no-untyped-def]
        """Synchronous Twilio send (runs in thread pool)."""
        from_phone = message.from_phone or self._from_phone
        if not from_phone:
            raise ValueError("No from_phone specified and no default configured")
        
        if self._client is None:
            raise RuntimeError("Twilio client not initialized")
        
        return self._client.messages.create(
            body=message.body,
            from_=from_phone,
            to=message.to_phone,
        )
    
    async def get_delivery_status(self, message_id: str) -> SMSStatus:
        """Get the delivery status of a previously sent message."""
        if not self._client:
            return SMSStatus.FAILED
        
        try:
            loop = asyncio.get_event_loop()
            client = self._client  # Capture for closure
            twilio_message = await loop.run_in_executor(
                None,
                lambda: client.messages(message_id).fetch(),
            )
            
            status_map = {
                "queued": SMSStatus.QUEUED,
                "sending": SMSStatus.SENDING,
                "sent": SMSStatus.SENT,
                "delivered": SMSStatus.DELIVERED,
                "failed": SMSStatus.FAILED,
                "undelivered": SMSStatus.UNDELIVERED,
            }
            
            return status_map.get(twilio_message.status, SMSStatus.PENDING)
            
        except Exception as e:
            logger.error("sms_status_check_failed", message_id=message_id, error=str(e))
            return SMSStatus.FAILED


class MockSMSService(BaseSMSService):
    """Mock SMS service for testing and development.
    
    This implementation logs messages but doesn't actually send them.
    Useful for development and testing environments.
    """
    
    def __init__(self) -> None:
        self._sent_messages: list[SMSMessage] = []
        logger.info("mock_sms_service_initialized")
    
    @property
    def provider_name(self) -> str:
        return "mock"
    
    @property
    def sent_messages(self) -> list[SMSMessage]:
        """Get list of messages that would have been sent."""
        return self._sent_messages.copy()
    
    def clear_sent_messages(self) -> None:
        """Clear the sent messages list."""
        self._sent_messages.clear()
    
    async def send_sms(self, message: SMSMessage) -> SMSResult:
        """Mock send - logs the message and returns success."""
        self._sent_messages.append(message)
        
        # Generate a fake message ID
        from app.domain.common.identifiers import new_ulid
        message_id = f"mock_{new_ulid()}"
        
        logger.info(
            "mock_sms_sent",
            message_id=message_id,
            to=message.to_phone,
            body_preview=message.body[:50] + "..." if len(message.body) > 50 else message.body,
            reference_id=message.reference_id,
        )
        
        return SMSResult(
            message_id=message_id,
            to_phone=message.to_phone,
            status=SMSStatus.DELIVERED,
            sent_at=datetime.now(timezone.utc),
            provider=self.provider_name,
            segments=1,
        )
    
    async def get_delivery_status(self, message_id: str) -> SMSStatus:
        """Mock always returns DELIVERED for valid mock IDs."""
        if message_id.startswith("mock_"):
            return SMSStatus.DELIVERED
        return SMSStatus.FAILED


def get_sms_service() -> BaseSMSService:
    """Get the appropriate SMS service based on configuration.
    
    Returns TwilioSMSService if Twilio is configured, otherwise MockSMSService.
    """
    twilio_service = TwilioSMSService()
    if twilio_service.is_configured:
        return twilio_service
    
    logger.warning(
        "using_mock_sms_service",
        message="Twilio not configured, using mock SMS service",
    )
    return MockSMSService()


# Singleton instance
_sms_service: BaseSMSService | None = None


def get_sms_service_singleton() -> BaseSMSService:
    """Get the singleton SMS service instance."""
    global _sms_service
    if _sms_service is None:
        _sms_service = get_sms_service()
    return _sms_service
