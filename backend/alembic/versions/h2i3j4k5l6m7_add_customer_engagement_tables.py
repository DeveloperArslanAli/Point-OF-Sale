"""Add customer engagement tables

Revision ID: h2i3j4k5l6m7
Revises: g1h2i3j4k5l6
Create Date: 2024-01-15 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "h2i3j4k5l6m7"
down_revision: Union[str, None] = "g1h2i3j4k5l6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create enum types
    loyalty_tier_enum = postgresql.ENUM(
        "bronze", "silver", "gold", "platinum",
        name="loyalty_tier",
        create_type=False,
    )
    loyalty_tier_enum.create(op.get_bind(), checkfirst=True)

    point_transaction_type_enum = postgresql.ENUM(
        "earn", "redeem", "bonus", "expire", "adjust", "refund",
        name="point_transaction_type",
        create_type=False,
    )
    point_transaction_type_enum.create(op.get_bind(), checkfirst=True)

    engagement_event_type_enum = postgresql.ENUM(
        "purchase", "repeat_purchase", "high_value_purchase",
        "account_created", "profile_updated", "loyalty_enrolled", "tier_upgraded",
        "visited_store", "app_login", "email_opened", "email_clicked", "survey_completed",
        "points_earned", "points_redeemed", "coupon_used", "gift_card_purchased", "gift_card_redeemed",
        "review_submitted", "feedback_given", "complaint_filed",
        "inactive_warning", "win_back_attempt",
        name="engagement_event_type",
        create_type=False,
    )
    engagement_event_type_enum.create(op.get_bind(), checkfirst=True)

    customer_segment_enum = postgresql.ENUM(
        "new", "active", "engaged", "loyal", "vip", "at_risk", "churned", "win_back",
        name="customer_segment",
        create_type=False,
    )
    customer_segment_enum.create(op.get_bind(), checkfirst=True)

    notification_type_enum = postgresql.ENUM(
        "order_confirmation", "order_receipt", "refund_processed", "payment_received",
        "points_earned", "points_expiring", "tier_upgrade", "tier_downgrade_warning", "reward_available",
        "promotional", "new_product", "flash_sale", "birthday_reward", "anniversary_reward",
        "welcome", "win_back", "feedback_request", "survey",
        "gift_card_received", "gift_card_low_balance", "gift_card_expiring",
        name="notification_type",
        create_type=False,
    )
    notification_type_enum.create(op.get_bind(), checkfirst=True)

    notification_channel_enum = postgresql.ENUM(
        "email", "sms", "push", "in_app",
        name="notification_channel",
        create_type=False,
    )
    notification_channel_enum.create(op.get_bind(), checkfirst=True)

    notification_status_enum = postgresql.ENUM(
        "pending", "queued", "sent", "delivered", "opened", "clicked", "bounced", "failed", "unsubscribed",
        name="notification_status",
        create_type=False,
    )
    notification_status_enum.create(op.get_bind(), checkfirst=True)

    notification_priority_enum = postgresql.ENUM(
        "low", "normal", "high", "urgent",
        name="notification_priority",
        create_type=False,
    )
    notification_priority_enum.create(op.get_bind(), checkfirst=True)

    # Create loyalty_accounts table
    op.create_table(
        "loyalty_accounts",
        sa.Column("id", sa.String(26), primary_key=True),
        sa.Column("customer_id", sa.String(26), sa.ForeignKey("customers.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("current_points", sa.Integer(), nullable=False, default=0),
        sa.Column("lifetime_points", sa.Integer(), nullable=False, default=0),
        sa.Column("tier", loyalty_tier_enum, nullable=False, server_default="bronze"),
        sa.Column("enrolled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, default=0),
        sa.Column("tenant_id", sa.String(26), nullable=True, index=True),
    )
    op.create_index("ix_loyalty_accounts_customer_id", "loyalty_accounts", ["customer_id"])

    # Create loyalty_point_transactions table
    op.create_table(
        "loyalty_point_transactions",
        sa.Column("id", sa.String(26), primary_key=True),
        sa.Column("loyalty_account_id", sa.String(26), sa.ForeignKey("loyalty_accounts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("transaction_type", point_transaction_type_enum, nullable=False),
        sa.Column("points", sa.Integer(), nullable=False),
        sa.Column("balance_after", sa.Integer(), nullable=False),
        sa.Column("reference_id", sa.String(26), nullable=True),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("tenant_id", sa.String(26), nullable=True, index=True),
    )
    op.create_index("ix_loyalty_point_transactions_loyalty_account_id", "loyalty_point_transactions", ["loyalty_account_id"])
    op.create_index("ix_loyalty_point_transactions_reference_id", "loyalty_point_transactions", ["reference_id"])
    op.create_index("ix_loyalty_point_transactions_created_at", "loyalty_point_transactions", ["created_at"])

    # Create engagement_events table
    op.create_table(
        "engagement_events",
        sa.Column("id", sa.String(26), primary_key=True),
        sa.Column("customer_id", sa.String(26), nullable=False),
        sa.Column("event_type", engagement_event_type_enum, nullable=False),
        sa.Column("reference_id", sa.String(26), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("tenant_id", sa.String(26), nullable=True, index=True),
    )
    op.create_index("ix_engagement_events_customer_id", "engagement_events", ["customer_id"])
    op.create_index("ix_engagement_events_event_type", "engagement_events", ["event_type"])
    op.create_index("ix_engagement_events_reference_id", "engagement_events", ["reference_id"])
    op.create_index("ix_engagement_events_created_at", "engagement_events", ["created_at"])

    # Create customer_engagement_profiles table
    op.create_table(
        "customer_engagement_profiles",
        sa.Column("id", sa.String(26), primary_key=True),
        sa.Column("customer_id", sa.String(26), nullable=False, unique=True),
        sa.Column("segment", customer_segment_enum, nullable=False, server_default="new"),
        sa.Column("total_purchases", sa.Integer(), nullable=False, default=0),
        sa.Column("total_spent", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("average_order_value", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("last_purchase_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("total_interactions", sa.Integer(), nullable=False, default=0),
        sa.Column("last_interaction_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("email_open_rate", sa.Float(), nullable=False, default=0.0),
        sa.Column("email_click_rate", sa.Float(), nullable=False, default=0.0),
        sa.Column("loyalty_tier", sa.String(20), nullable=True),
        sa.Column("current_points", sa.Integer(), nullable=False, default=0),
        sa.Column("lifetime_points", sa.Integer(), nullable=False, default=0),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, default=0),
        sa.Column("tenant_id", sa.String(26), nullable=True, index=True),
    )
    op.create_index("ix_customer_engagement_profiles_customer_id", "customer_engagement_profiles", ["customer_id"])
    op.create_index("ix_customer_engagement_profiles_segment", "customer_engagement_profiles", ["segment"])

    # Create notification_templates table
    op.create_table(
        "notification_templates",
        sa.Column("id", sa.String(26), primary_key=True),
        sa.Column("name", sa.String(120), nullable=False, unique=True),
        sa.Column("notification_type", notification_type_enum, nullable=False),
        sa.Column("channel", notification_channel_enum, nullable=False),
        sa.Column("subject", sa.String(255), nullable=True),
        sa.Column("body_template", sa.Text(), nullable=False),
        sa.Column("variables", postgresql.ARRAY(sa.String()), nullable=False, server_default="{}"),
        sa.Column("is_active", sa.Boolean(), nullable=False, default=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, default=0),
        sa.Column("tenant_id", sa.String(26), nullable=True, index=True),
    )
    op.create_index("ix_notification_templates_name", "notification_templates", ["name"])
    op.create_index("ix_notification_templates_notification_type", "notification_templates", ["notification_type"])

    # Create customer_notifications table
    op.create_table(
        "customer_notifications",
        sa.Column("id", sa.String(26), primary_key=True),
        sa.Column("customer_id", sa.String(26), nullable=False),
        sa.Column("notification_type", notification_type_enum, nullable=False),
        sa.Column("channel", notification_channel_enum, nullable=False),
        sa.Column("priority", notification_priority_enum, nullable=False, server_default="normal"),
        sa.Column("subject", sa.String(255), nullable=True),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("status", notification_status_enum, nullable=False, server_default="pending"),
        sa.Column("reference_id", sa.String(26), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(), nullable=True),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("clicked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failed_reason", sa.Text(), nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=False, default=0),
        sa.Column("max_retries", sa.Integer(), nullable=False, default=3),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, default=0),
        sa.Column("tenant_id", sa.String(26), nullable=True, index=True),
    )
    op.create_index("ix_customer_notifications_customer_id", "customer_notifications", ["customer_id"])
    op.create_index("ix_customer_notifications_notification_type", "customer_notifications", ["notification_type"])
    op.create_index("ix_customer_notifications_status", "customer_notifications", ["status"])
    op.create_index("ix_customer_notifications_reference_id", "customer_notifications", ["reference_id"])
    op.create_index("ix_customer_notifications_scheduled_at", "customer_notifications", ["scheduled_at"])
    op.create_index("ix_customer_notifications_created_at", "customer_notifications", ["created_at"])

    # Create customer_notification_preferences table
    op.create_table(
        "customer_notification_preferences",
        sa.Column("id", sa.String(26), primary_key=True),
        sa.Column("customer_id", sa.String(26), nullable=False, unique=True),
        sa.Column("email_enabled", sa.Boolean(), nullable=False, default=True),
        sa.Column("sms_enabled", sa.Boolean(), nullable=False, default=False),
        sa.Column("push_enabled", sa.Boolean(), nullable=False, default=False),
        sa.Column("in_app_enabled", sa.Boolean(), nullable=False, default=True),
        sa.Column("transactional_enabled", sa.Boolean(), nullable=False, default=True),
        sa.Column("loyalty_enabled", sa.Boolean(), nullable=False, default=True),
        sa.Column("marketing_enabled", sa.Boolean(), nullable=False, default=True),
        sa.Column("engagement_enabled", sa.Boolean(), nullable=False, default=True),
        sa.Column("quiet_hours_start", sa.Integer(), nullable=True),
        sa.Column("quiet_hours_end", sa.Integer(), nullable=True),
        sa.Column("timezone", sa.String(50), nullable=False, server_default="UTC"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, default=0),
        sa.Column("tenant_id", sa.String(26), nullable=True, index=True),
    )
    op.create_index("ix_customer_notification_preferences_customer_id", "customer_notification_preferences", ["customer_id"])


def downgrade() -> None:
    # Drop tables
    op.drop_table("customer_notification_preferences")
    op.drop_table("customer_notifications")
    op.drop_table("notification_templates")
    op.drop_table("customer_engagement_profiles")
    op.drop_table("engagement_events")
    op.drop_table("loyalty_point_transactions")
    op.drop_table("loyalty_accounts")

    # Drop enum types
    op.execute("DROP TYPE IF EXISTS notification_priority")
    op.execute("DROP TYPE IF EXISTS notification_status")
    op.execute("DROP TYPE IF EXISTS notification_channel")
    op.execute("DROP TYPE IF EXISTS notification_type")
    op.execute("DROP TYPE IF EXISTS customer_segment")
    op.execute("DROP TYPE IF EXISTS engagement_event_type")
    op.execute("DROP TYPE IF EXISTS point_transaction_type")
    op.execute("DROP TYPE IF EXISTS loyalty_tier")
