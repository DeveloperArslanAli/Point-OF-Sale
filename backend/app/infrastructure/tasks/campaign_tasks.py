"""Celery tasks for marketing campaigns and customer engagement."""
from __future__ import annotations

import structlog
from datetime import UTC, datetime, timedelta
from typing import Any

from app.core.settings import get_settings
from app.infrastructure.tasks.celery_app import celery_app
from app.infrastructure.tasks.email_tasks import send_email

logger = structlog.get_logger(__name__)
settings = get_settings()


@celery_app.task(name="run_scheduled_campaigns")
def run_scheduled_campaigns() -> dict[str, Any]:
    """
    Check and execute campaigns that are scheduled to run.
    This task should be run every 5 minutes via Celery Beat.
    """
    import asyncio
    from app.infrastructure.db.session import async_session_factory
    from app.infrastructure.db.repositories.campaign_repository import (
        SqlAlchemyCampaignRepository,
    )

    async def _run() -> dict[str, Any]:
        async with async_session_factory() as session:
            repo = SqlAlchemyCampaignRepository(session)
            campaigns = await repo.get_scheduled_to_run()

            started = []
            for campaign in campaigns:
                try:
                    campaign.start()
                    await repo.update(campaign)
                    started.append(campaign.id)

                    # Queue the campaign execution
                    execute_campaign.delay(campaign.id)

                    logger.info(
                        "campaign_started",
                        campaign_id=campaign.id,
                        campaign_name=campaign.name,
                    )
                except Exception as e:
                    logger.error(
                        "campaign_start_failed",
                        campaign_id=campaign.id,
                        error=str(e),
                    )

            await session.commit()
            return {"started_campaigns": started, "count": len(started)}

    return asyncio.run(_run())


@celery_app.task(bind=True, name="execute_campaign", max_retries=3)
def execute_campaign(self, campaign_id: str) -> dict[str, Any]:
    """
    Execute a marketing campaign by sending notifications to recipients.
    """
    import asyncio
    from app.infrastructure.db.session import async_session_factory
    from app.infrastructure.db.repositories.campaign_repository import (
        SqlAlchemyCampaignRepository,
        SqlAlchemyCampaignRecipientRepository,
    )
    from app.infrastructure.db.repositories.notification_repository import (
        SqlAlchemyCustomerNotificationRepository,
        SqlAlchemyNotificationPreferencesRepository,
    )
    from app.infrastructure.db.repositories.customer_repository import (
        SqlAlchemyCustomerRepository,
    )
    from app.domain.customers.notifications import (
        CustomerNotification,
        NotificationChannel,
        NotificationPriority,
        NotificationType,
    )

    async def _execute() -> dict[str, Any]:
        async with async_session_factory() as session:
            campaign_repo = SqlAlchemyCampaignRepository(session)
            recipient_repo = SqlAlchemyCampaignRecipientRepository(session)
            notification_repo = SqlAlchemyCustomerNotificationRepository(session)
            prefs_repo = SqlAlchemyNotificationPreferencesRepository(session)
            customer_repo = SqlAlchemyCustomerRepository(session)

            campaign = await campaign_repo.get_by_id(campaign_id)
            if not campaign:
                logger.error("campaign_not_found", campaign_id=campaign_id)
                return {"error": "Campaign not found"}

            if campaign.status.value != "running":
                logger.warning(
                    "campaign_not_running",
                    campaign_id=campaign_id,
                    status=campaign.status.value,
                )
                return {"error": f"Campaign status is {campaign.status.value}"}

            # Get pending recipients
            recipients = await recipient_repo.get_pending_for_campaign(
                campaign_id, limit=campaign.send_rate_limit
            )

            sent_count = 0
            failed_count = 0

            for recipient in recipients:
                try:
                    # Get customer
                    customer = await customer_repo.get_by_id(recipient.customer_id)
                    if not customer:
                        continue

                    # Check preferences
                    prefs = await prefs_repo.get_or_create(recipient.customer_id)

                    # Determine channel and notification type
                    channel = NotificationChannel.EMAIL
                    if campaign.campaign_type.value == "sms":
                        channel = NotificationChannel.SMS
                    elif campaign.campaign_type.value == "push":
                        channel = NotificationChannel.PUSH

                    notification_type = NotificationType.PROMOTIONAL

                    # Check if customer can receive this notification
                    if not prefs.can_receive(channel, notification_type):
                        recipient.status = "skipped"
                        await recipient_repo.update(recipient)
                        continue

                    # Create notification
                    notification = CustomerNotification.create(
                        customer_id=recipient.customer_id,
                        notification_type=notification_type,
                        channel=channel,
                        subject=campaign.content.subject,
                        body=campaign.content.body,
                        priority=NotificationPriority.NORMAL,
                        reference_id=campaign.id,
                        metadata={"campaign_id": campaign.id, "campaign_name": campaign.name},
                    )

                    await notification_repo.save(notification)

                    # Send via appropriate channel
                    if channel == NotificationChannel.EMAIL:
                        send_email.delay(
                            to=customer.email,
                            subject=campaign.content.subject or "Special Offer",
                            body=campaign.content.body,
                            html=campaign.content.html_body,
                        )

                    recipient.mark_sent(notification.id)
                    await recipient_repo.update(recipient)
                    sent_count += 1

                except Exception as e:
                    logger.error(
                        "recipient_send_failed",
                        recipient_id=recipient.id,
                        error=str(e),
                    )
                    failed_count += 1

            # Update campaign metrics
            campaign.metrics.record_sent(sent_count)
            campaign.metrics.total_failed += failed_count
            await campaign_repo.update(campaign)

            # Check if all recipients processed
            status_counts = await recipient_repo.count_by_status(campaign_id)
            pending_count = status_counts.get("pending", 0)

            if pending_count == 0:
                campaign.complete()
                await campaign_repo.update(campaign)
                logger.info(
                    "campaign_completed",
                    campaign_id=campaign_id,
                    total_sent=campaign.metrics.total_sent,
                )
            elif sent_count > 0:
                # More recipients to process, schedule next batch
                execute_campaign.apply_async(
                    args=[campaign_id],
                    countdown=60,  # Wait 1 minute before next batch
                )

            await session.commit()
            return {
                "campaign_id": campaign_id,
                "sent": sent_count,
                "failed": failed_count,
                "remaining": pending_count,
            }

    try:
        return asyncio.run(_execute())
    except Exception as exc:
        logger.error("campaign_execution_failed", campaign_id=campaign_id, error=str(exc))
        raise self.retry(exc=exc, countdown=300)


@celery_app.task(name="send_birthday_notifications")
def send_birthday_notifications() -> dict[str, Any]:
    """
    Send birthday notifications to customers.
    This task should run daily (e.g., at 8 AM).
    """
    import asyncio
    from app.infrastructure.db.session import async_session_factory
    from app.infrastructure.db.repositories.customer_repository import (
        SqlAlchemyCustomerRepository,
    )
    from app.infrastructure.db.repositories.notification_repository import (
        SqlAlchemyCustomerNotificationRepository,
        SqlAlchemyNotificationPreferencesRepository,
    )
    from app.domain.customers.notifications import (
        CustomerNotification,
        NotificationChannel,
        NotificationPriority,
        NotificationType,
    )

    async def _send_birthdays() -> dict[str, Any]:
        async with async_session_factory() as session:
            customer_repo = SqlAlchemyCustomerRepository(session)
            notification_repo = SqlAlchemyCustomerNotificationRepository(session)
            prefs_repo = SqlAlchemyNotificationPreferencesRepository(session)

            # Get customers with birthdays today
            # Note: This would require a birthday field on Customer entity
            # For now, we'll log and return
            logger.info("birthday_notification_task_started")

            # TODO: Implement once birthday field is added to Customer
            # today = datetime.now(UTC).date()
            # customers = await customer_repo.get_by_birthday_month_day(
            #     month=today.month, day=today.day
            # )

            sent_count = 0
            await session.commit()
            return {"sent": sent_count}

    return asyncio.run(_send_birthdays())


@celery_app.task(name="send_win_back_notifications")
def send_win_back_notifications() -> dict[str, Any]:
    """
    Send win-back notifications to inactive customers.
    This task should run weekly.
    """
    import asyncio
    from app.infrastructure.db.session import async_session_factory
    from app.infrastructure.db.repositories.engagement_repository import (
        SqlAlchemyEngagementProfileRepository,
    )
    from app.infrastructure.db.repositories.customer_repository import (
        SqlAlchemyCustomerRepository,
    )
    from app.infrastructure.db.repositories.notification_repository import (
        SqlAlchemyCustomerNotificationRepository,
        SqlAlchemyNotificationPreferencesRepository,
    )
    from app.domain.customers.notifications import (
        CustomerNotification,
        NotificationChannel,
        NotificationPriority,
        NotificationType,
    )

    async def _send_win_backs() -> dict[str, Any]:
        async with async_session_factory() as session:
            profile_repo = SqlAlchemyEngagementProfileRepository(session)
            customer_repo = SqlAlchemyCustomerRepository(session)
            notification_repo = SqlAlchemyCustomerNotificationRepository(session)
            prefs_repo = SqlAlchemyNotificationPreferencesRepository(session)

            # Get at-risk customers
            at_risk_profiles = await profile_repo.list_at_risk_customers(
                inactive_days=60, limit=100
            )

            sent_count = 0
            for profile in at_risk_profiles:
                try:
                    customer = await customer_repo.get_by_id(profile.customer_id)
                    if not customer or not customer.active:
                        continue

                    prefs = await prefs_repo.get_or_create(profile.customer_id)
                    if not prefs.can_receive(
                        NotificationChannel.EMAIL, NotificationType.WIN_BACK
                    ):
                        continue

                    notification = CustomerNotification.create(
                        customer_id=profile.customer_id,
                        notification_type=NotificationType.WIN_BACK,
                        channel=NotificationChannel.EMAIL,
                        subject="We miss you! Here's a special offer",
                        body=f"Hi {customer.first_name}, we noticed you haven't visited in a while. Come back and enjoy a special 15% discount on your next purchase!",
                        priority=NotificationPriority.NORMAL,
                        metadata={"days_inactive": 60},
                    )

                    await notification_repo.save(notification)

                    send_email.delay(
                        to=customer.email,
                        subject=notification.subject,
                        body=notification.body,
                    )

                    sent_count += 1

                except Exception as e:
                    logger.error(
                        "win_back_notification_failed",
                        customer_id=profile.customer_id,
                        error=str(e),
                    )

            await session.commit()
            logger.info("win_back_notifications_sent", count=sent_count)
            return {"sent": sent_count}

    return asyncio.run(_send_win_backs())


@celery_app.task(name="process_pending_notifications")
def process_pending_notifications() -> dict[str, Any]:
    """
    Process pending notifications and send them.
    This task should run every minute.
    """
    import asyncio
    from app.infrastructure.db.session import async_session_factory
    from app.infrastructure.db.repositories.notification_repository import (
        SqlAlchemyCustomerNotificationRepository,
    )
    from app.infrastructure.db.repositories.customer_repository import (
        SqlAlchemyCustomerRepository,
    )
    from app.domain.customers.notifications import NotificationChannel

    async def _process() -> dict[str, Any]:
        async with async_session_factory() as session:
            notification_repo = SqlAlchemyCustomerNotificationRepository(session)
            customer_repo = SqlAlchemyCustomerRepository(session)

            # Get pending notifications
            pending = await notification_repo.get_pending_for_sending(limit=100)

            sent_count = 0
            failed_count = 0

            for notification in pending:
                try:
                    customer = await customer_repo.get_by_id(notification.customer_id)
                    if not customer:
                        notification.mark_failed("Customer not found")
                        await notification_repo.update(notification)
                        failed_count += 1
                        continue

                    notification.queue()
                    await notification_repo.update(notification)

                    if notification.channel == NotificationChannel.EMAIL:
                        send_email.delay(
                            to=customer.email,
                            subject=notification.subject or "Notification",
                            body=notification.body,
                        )
                        notification.mark_sent()
                    elif notification.channel == NotificationChannel.SMS:
                        # TODO: Implement SMS sending
                        send_sms_notification.delay(
                            phone=customer.phone or "",
                            message=notification.body,
                        )
                        notification.mark_sent()
                    else:
                        # In-app or push notifications handled differently
                        notification.mark_sent()

                    await notification_repo.update(notification)
                    sent_count += 1

                except Exception as e:
                    logger.error(
                        "notification_send_failed",
                        notification_id=notification.id,
                        error=str(e),
                    )
                    notification.mark_failed(str(e))
                    await notification_repo.update(notification)
                    failed_count += 1

            await session.commit()
            return {"sent": sent_count, "failed": failed_count}

    return asyncio.run(_process())


@celery_app.task(name="retry_failed_notifications")
def retry_failed_notifications() -> dict[str, Any]:
    """
    Retry failed notifications that are eligible for retry.
    This task should run every 15 minutes.
    """
    import asyncio
    from app.infrastructure.db.session import async_session_factory
    from app.infrastructure.db.repositories.notification_repository import (
        SqlAlchemyCustomerNotificationRepository,
    )
    from app.domain.customers.notifications import NotificationStatus

    async def _retry() -> dict[str, Any]:
        async with async_session_factory() as session:
            notification_repo = SqlAlchemyCustomerNotificationRepository(session)

            # Get failed notifications eligible for retry
            failed = await notification_repo.get_failed_for_retry(limit=50)

            requeued_count = 0
            for notification in failed:
                try:
                    # Reset to pending for reprocessing
                    notification.status = NotificationStatus.PENDING
                    await notification_repo.update(notification)
                    requeued_count += 1
                except Exception as e:
                    logger.error(
                        "notification_requeue_failed",
                        notification_id=notification.id,
                        error=str(e),
                    )

            await session.commit()
            return {"requeued": requeued_count}

    return asyncio.run(_retry())


@celery_app.task(name="send_sms_notification", max_retries=3)
def send_sms_notification(phone: str, message: str, reference_id: str | None = None) -> dict[str, str]:
    """
    Send SMS notification using the configured SMS service.
    Supports Twilio or falls back to mock service in development.
    """
    import asyncio
    from app.infrastructure.services.sms_service import (
        SMSMessage,
        get_sms_service_singleton,
    )

    logger.info("sending_sms", phone=phone[:4] + "****" if len(phone) > 4 else phone, message_length=len(message))

    async def _send() -> dict[str, str]:
        sms_service = get_sms_service_singleton()

        try:
            sms_message = SMSMessage(
                to_phone=phone,
                body=message,
                reference_id=reference_id,
            )
            result = await sms_service.send_sms(sms_message)

            return {
                "status": result.status.value,
                "message_id": result.message_id or "",
                "phone": phone,
                "provider": result.provider,
            }
        except ValueError as e:
            logger.warning("sms_validation_error", error=str(e))
            return {"status": "failed", "error": str(e), "phone": phone}

    return asyncio.run(_send())


@celery_app.task(name="update_engagement_profiles")
def update_engagement_profiles() -> dict[str, Any]:
    """
    Update customer engagement profiles based on recent activity.
    This task should run daily.
    """
    import asyncio
    from app.infrastructure.db.session import async_session_factory
    from app.infrastructure.db.repositories.engagement_repository import (
        SqlAlchemyEngagementProfileRepository,
        SqlAlchemyEngagementEventRepository,
    )
    from app.infrastructure.db.repositories.notification_repository import (
        SqlAlchemyCustomerNotificationRepository,
    )
    from app.domain.customers.engagement import CustomerSegment

    async def _update() -> dict[str, Any]:
        async with async_session_factory() as session:
            profile_repo = SqlAlchemyEngagementProfileRepository(session)
            event_repo = SqlAlchemyEngagementEventRepository(session)
            notification_repo = SqlAlchemyCustomerNotificationRepository(session)

            # Get segment counts for logging
            segment_counts = await profile_repo.count_by_segment()

            # Update email engagement metrics
            # This would iterate through profiles and update based on recent notifications
            logger.info(
                "engagement_profiles_updated",
                segment_counts={k.value: v for k, v in segment_counts.items()},
            )

            await session.commit()
            return {"segment_counts": {k.value: v for k, v in segment_counts.items()}}

    return asyncio.run(_update())
