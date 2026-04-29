"""
Event dispatcher for WebSocket real-time communication.

Integrates Redis pub/sub with WebSocket connection manager
to broadcast events across distributed backend instances.
"""

import asyncio
import json
from typing import Optional, Callable, Awaitable
import structlog

import redis.asyncio as redis
from redis.exceptions import ConnectionError as RedisConnectionError

from .connection_manager import ConnectionManager
from .events import WebSocketEvent, EventType

logger = structlog.get_logger(__name__)


class EventDispatcher:
    """
    Dispatches events from Redis pub/sub to WebSocket connections.

    Features:
    - Redis pub/sub integration
    - Event filtering by tenant
    - Graceful shutdown
    - Error handling and reconnection
    """

    def __init__(
        self,
        connection_manager: ConnectionManager,
        redis_url: str = "redis://localhost:6379/0",
    ):
        """
        Initialize event dispatcher.

        Args:
            connection_manager: ConnectionManager instance to broadcast to
            redis_url: Redis connection URL
        """
        self._connection_manager = connection_manager
        self._redis_url = redis_url
        self._redis_client: Optional[redis.Redis] = None
        self._pubsub: Optional[redis.client.PubSub] = None
        self._listening_task: Optional[asyncio.Task] = None
        self._running = False

        # Channel naming convention: "pos:events:{tenant_id}"
        # Global channel: "pos:events:global"
        self._channel_prefix = "pos:events:"

    async def start(self) -> bool:
        """Start the event dispatcher and begin listening to Redis."""
        if self._running:
            logger.warning("event_dispatcher_already_running")
            return True

        # Skip when Redis is not configured
        if not self._redis_url:
            logger.warning("event_dispatcher_disabled", reason="redis_url_missing")
            return False

        try:
            # Connect to Redis
            self._redis_client = redis.from_url(
                self._redis_url,
                encoding="utf-8",
                decode_responses=True,
            )

            # Create pub/sub instance
            self._pubsub = self._redis_client.pubsub()

            # Subscribe to global channel
            await self._pubsub.psubscribe(f"{self._channel_prefix}*")

            # Start listening task
            self._running = True
            self._listening_task = asyncio.create_task(self._listen_loop())

            logger.info(
                "event_dispatcher_started",
                redis_url=self._redis_url,
                channel_pattern=f"{self._channel_prefix}*",
            )

            return True

        except RedisConnectionError as e:
            await self._cleanup_failed_start()
            logger.warning(
                "event_dispatcher_start_skipped",
                redis_url=self._redis_url,
                error=str(e),
            )
            return False

        except Exception as e:
            await self._cleanup_failed_start()
            logger.error("event_dispatcher_start_failed", error=str(e), exc_info=True)
            raise

    async def stop(self) -> None:
        """Stop the event dispatcher and cleanup resources."""
        if not self._running:
            return

        self._running = False

        # Cancel listening task
        if self._listening_task and not self._listening_task.done():
            self._listening_task.cancel()
            try:
                await self._listening_task
            except asyncio.CancelledError:
                pass

        # Cleanup Redis
        if self._pubsub:
            await self._pubsub.unsubscribe()
            await self._pubsub.close()

        if self._redis_client:
            await self._redis_client.close()

        logger.info("event_dispatcher_stopped")

    async def _cleanup_failed_start(self) -> None:
        """Clean up resources when startup fails."""
        if self._listening_task and not self._listening_task.done():
            self._listening_task.cancel()
            try:
                await self._listening_task
            except asyncio.CancelledError:
                pass
        self._listening_task = None

        if self._pubsub:
            try:
                await self._pubsub.close()
            except Exception:
                logger.debug("event_dispatcher_pubsub_cleanup_failed", exc_info=True)
        self._pubsub = None

        if self._redis_client:
            try:
                await self._redis_client.close()
            except Exception:
                logger.debug("event_dispatcher_client_cleanup_failed", exc_info=True)
        self._redis_client = None

    async def _listen_loop(self) -> None:
        """Internal loop to listen for Redis pub/sub messages."""
        logger.info("event_dispatcher_listen_loop_started")

        try:
            async for message in self._pubsub.listen():
                if not self._running:
                    break

                if message["type"] != "pmessage":
                    continue

                try:
                    # Parse event
                    channel = message["channel"]
                    data = message["data"]
                    event_dict = json.loads(data)

                    event = WebSocketEvent(**event_dict)

                    # Extract tenant_id from channel
                    # Channel format: pos:events:{tenant_id} or pos:events:global
                    tenant_id = channel.replace(self._channel_prefix, "")

                    # Broadcast to WebSocket clients
                    if tenant_id == "global":
                        # Broadcast to all tenants
                        for t_id in self._connection_manager._connections.keys():
                            await self._connection_manager.broadcast_to_tenant(
                                tenant_id=t_id,
                                event=event,
                            )
                    else:
                        # Broadcast to specific tenant
                        await self._connection_manager.broadcast_to_tenant(
                            tenant_id=tenant_id,
                            event=event,
                        )

                    logger.debug(
                        "event_dispatched",
                        channel=channel,
                        event_type=event.type,
                        tenant_id=tenant_id,
                    )

                except json.JSONDecodeError as e:
                    logger.error(
                        "event_parse_failed",
                        error=str(e),
                        data=message.get("data"),
                    )
                except Exception as e:
                    logger.error(
                        "event_dispatch_failed",
                        error=str(e),
                        exc_info=True,
                    )

        except asyncio.CancelledError:
            logger.info("event_dispatcher_listen_loop_cancelled")
            raise
        except Exception as e:
            logger.error(
                "event_dispatcher_listen_loop_error",
                error=str(e),
                exc_info=True,
            )
        finally:
            logger.info("event_dispatcher_listen_loop_ended")

    async def publish_event(
        self,
        event: WebSocketEvent,
        tenant_id: Optional[str] = None,
    ) -> None:
        """
        Publish an event to Redis for distribution to WebSocket clients.

        Args:
            event: Event to publish
            tenant_id: Target tenant ID (None for global broadcast)
        """
        if not self._redis_client:
            # Fallback to in-process broadcast so tests/dev still see events
            target_tenant = tenant_id or event.tenant_id or "default"
            await self._connection_manager.broadcast_to_tenant(
                tenant_id=target_tenant,
                event=event,
            )
            logger.debug(
                "event_published_local_only",
                event_type=event.type,
                tenant_id=target_tenant,
            )
            return

        try:
            # Determine channel
            channel = (
                f"{self._channel_prefix}{tenant_id}"
                if tenant_id
                else f"{self._channel_prefix}global"
            )

            # Publish to Redis
            await self._redis_client.publish(
                channel,
                event.model_dump_json(),
            )

            logger.debug(
                "event_published",
                channel=channel,
                event_type=event.type,
                tenant_id=tenant_id,
            )

        except Exception as e:
            logger.error(
                "event_publish_failed",
                error=str(e),
                event_type=event.type,
                tenant_id=tenant_id,
                exc_info=True,
            )

    async def publish_to_role(
        self,
        event: WebSocketEvent,
        tenant_id: str,
        role: str,
    ) -> None:
        """
        Publish an event targeted at a specific role.

        Note: This bypasses Redis and uses the connection manager directly
        since role-based filtering requires local connection metadata.

        Args:
            event: Event to publish
            tenant_id: Target tenant ID
            role: Target role
        """
        await self._connection_manager.broadcast_to_role(
            tenant_id=tenant_id,
            role=role,
            event=event,
        )

        logger.debug(
            "event_published_to_role",
            event_type=event.type,
            tenant_id=tenant_id,
            role=role,
        )


# Global event dispatcher instance (initialized in main.py)
_event_dispatcher: Optional["EventDispatcher | NoOpEventDispatcher"] = None


class NoOpEventDispatcher:
    """Fallback dispatcher used when Redis-backed dispatcher is not initialized (tests/dev)."""

    async def publish_event(self, event: WebSocketEvent, tenant_id: Optional[str] = None) -> None:  # pragma: no cover - trivial
        return

    async def publish_to_role(self, event: WebSocketEvent, tenant_id: str, role: str) -> None:  # pragma: no cover - trivial
        return


def get_event_dispatcher() -> EventDispatcher:
    """Get the global event dispatcher instance."""
    global _event_dispatcher
    if _event_dispatcher is None:
        _event_dispatcher = NoOpEventDispatcher()  # type: ignore[assignment]
        logger.warning("event_dispatcher_noop_fallback")
    return _event_dispatcher


def set_event_dispatcher(dispatcher: EventDispatcher) -> None:
    """Set the global event dispatcher instance."""
    global _event_dispatcher
    _event_dispatcher = dispatcher
