"""Add webhook system tables

Revision ID: i3j4k5l6m7n8
Revises: h2i3j4k5l6m7
Create Date: 2024-01-15 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "i3j4k5l6m7n8"
down_revision: Union[str, None] = "h2i3j4k5l6m7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create enum types
    webhook_status_enum = postgresql.ENUM(
        "active", "inactive", "suspended",
        name="webhook_status",
        create_type=False,
    )
    webhook_status_enum.create(op.get_bind(), checkfirst=True)

    webhook_event_type_enum = postgresql.ENUM(
        "sale.created", "sale.completed", "sale.voided",
        "inventory.low", "inventory.updated", "inventory.received",
        "customer.created", "customer.updated", "customer.deactivated",
        "order.created", "order.shipped", "order.delivered",
        "product.created", "product.updated", "product.deleted",
        "return.created", "return.approved", "return.completed",
        "employee.clock_in", "employee.clock_out",
        "loyalty.points_earned", "loyalty.tier_changed",
        "gift_card.created", "gift_card.redeemed",
        name="webhook_event_type",
        create_type=False,
    )
    webhook_event_type_enum.create(op.get_bind(), checkfirst=True)

    delivery_status_enum = postgresql.ENUM(
        "pending", "success", "failed", "retrying",
        name="delivery_status",
        create_type=False,
    )
    delivery_status_enum.create(op.get_bind(), checkfirst=True)

    # Create webhook_subscriptions table
    op.create_table(
        "webhook_subscriptions",
        sa.Column("id", sa.String(26), primary_key=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("url", sa.String(2048), nullable=False),
        sa.Column("secret", sa.String(128), nullable=False),
        sa.Column("events", postgresql.ARRAY(sa.String()), nullable=False),
        sa.Column("status", webhook_status_enum, nullable=False, server_default="active"),
        sa.Column("headers_json", postgresql.JSONB(), nullable=True),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("max_retries", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("retry_interval_seconds", sa.Integer(), nullable=False, server_default="60"),
        sa.Column("consecutive_failures", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failure_threshold", sa.Integer(), nullable=False, server_default="10"),
        sa.Column("last_failure_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("tenant_id", sa.String(26), nullable=True),
    )
    op.create_index("ix_webhook_subscriptions_name", "webhook_subscriptions", ["name"])
    op.create_index("ix_webhook_subscriptions_status", "webhook_subscriptions", ["status"])
    op.create_index("ix_webhook_subscriptions_tenant_id", "webhook_subscriptions", ["tenant_id"])

    # Create webhook_events table
    op.create_table(
        "webhook_events",
        sa.Column("id", sa.String(26), primary_key=True),
        sa.Column("event_type", webhook_event_type_enum, nullable=False),
        sa.Column("payload_json", postgresql.JSONB(), nullable=False),
        sa.Column("reference_id", sa.String(26), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("tenant_id", sa.String(26), nullable=True),
    )
    op.create_index("ix_webhook_events_event_type", "webhook_events", ["event_type"])
    op.create_index("ix_webhook_events_reference_id", "webhook_events", ["reference_id"])
    op.create_index("ix_webhook_events_created_at", "webhook_events", ["created_at"])
    op.create_index("ix_webhook_events_tenant_id", "webhook_events", ["tenant_id"])

    # Create webhook_deliveries table
    op.create_table(
        "webhook_deliveries",
        sa.Column("id", sa.String(26), primary_key=True),
        sa.Column("subscription_id", sa.String(26), nullable=False),
        sa.Column("event_id", sa.String(26), nullable=False),
        sa.Column("event_type", webhook_event_type_enum, nullable=False),
        sa.Column("url", sa.String(2048), nullable=False),
        sa.Column("status", delivery_status_enum, nullable=False, server_default="pending"),
        sa.Column("request_headers_json", postgresql.JSONB(), nullable=True),
        sa.Column("request_body", sa.Text(), nullable=False, server_default=""),
        sa.Column("response_status_code", sa.Integer(), nullable=True),
        sa.Column("response_body", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("attempt_number", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("tenant_id", sa.String(26), nullable=True),
    )
    op.create_index("ix_webhook_deliveries_subscription_id", "webhook_deliveries", ["subscription_id"])
    op.create_index("ix_webhook_deliveries_event_id", "webhook_deliveries", ["event_id"])
    op.create_index("ix_webhook_deliveries_status", "webhook_deliveries", ["status"])
    op.create_index("ix_webhook_deliveries_next_retry_at", "webhook_deliveries", ["next_retry_at"])
    op.create_index("ix_webhook_deliveries_created_at", "webhook_deliveries", ["created_at"])
    op.create_index("ix_webhook_deliveries_tenant_id", "webhook_deliveries", ["tenant_id"])


def downgrade() -> None:
    # Drop tables
    op.drop_table("webhook_deliveries")
    op.drop_table("webhook_events")
    op.drop_table("webhook_subscriptions")

    # Drop enum types
    op.execute("DROP TYPE IF EXISTS delivery_status")
    op.execute("DROP TYPE IF EXISTS webhook_event_type")
    op.execute("DROP TYPE IF EXISTS webhook_status")
