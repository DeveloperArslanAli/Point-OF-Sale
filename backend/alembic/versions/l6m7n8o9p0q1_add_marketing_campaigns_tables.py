"""Add marketing campaigns and customer feedback tables

Revision ID: l6m7n8o9p0q1
Revises: k5l6m7n8o9p0
Create Date: 2024-01-16 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "l6m7n8o9p0q1"
down_revision: Union[str, None] = "k5l6m7n8o9p0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create enum types
    campaign_type_enum = postgresql.ENUM(
        "email", "sms", "push", "combined",
        name="campaign_type",
        create_type=False,
    )
    campaign_type_enum.create(op.get_bind(), checkfirst=True)

    campaign_status_enum = postgresql.ENUM(
        "draft", "scheduled", "running", "paused", "completed", "cancelled",
        name="campaign_status",
        create_type=False,
    )
    campaign_status_enum.create(op.get_bind(), checkfirst=True)

    campaign_trigger_enum = postgresql.ENUM(
        "manual", "scheduled", "birthday", "anniversary",
        "win_back", "welcome", "post_purchase", "cart_abandonment",
        "loyalty_milestone", "segment_entry",
        name="campaign_trigger",
        create_type=False,
    )
    campaign_trigger_enum.create(op.get_bind(), checkfirst=True)

    recipient_status_enum = postgresql.ENUM(
        "pending", "sent", "delivered", "opened", "clicked", "bounced", "failed", "unsubscribed",
        name="recipient_status",
        create_type=False,
    )
    recipient_status_enum.create(op.get_bind(), checkfirst=True)

    feedback_type_enum = postgresql.ENUM(
        "review", "complaint", "suggestion", "question", "compliment",
        name="feedback_type",
        create_type=False,
    )
    feedback_type_enum.create(op.get_bind(), checkfirst=True)

    feedback_status_enum = postgresql.ENUM(
        "pending", "under_review", "in_progress", "resolved", "closed",
        name="feedback_status",
        create_type=False,
    )
    feedback_status_enum.create(op.get_bind(), checkfirst=True)

    feedback_sentiment_enum = postgresql.ENUM(
        "positive", "neutral", "negative",
        name="feedback_sentiment",
        create_type=False,
    )
    feedback_sentiment_enum.create(op.get_bind(), checkfirst=True)

    # Create marketing_campaigns table
    op.create_table(
        "marketing_campaigns",
        sa.Column("id", sa.String(26), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("campaign_type", campaign_type_enum, nullable=False),
        sa.Column("campaign_trigger", campaign_trigger_enum, nullable=False, server_default="manual"),
        sa.Column("status", campaign_status_enum, nullable=False, server_default="draft"),
        # Targeting criteria (JSONB)
        sa.Column("targeting_json", postgresql.JSONB(), nullable=True),
        # Content (JSONB) - subject, body, templates by channel
        sa.Column("content_json", postgresql.JSONB(), nullable=True),
        # Metrics (JSONB) - sent, delivered, opened, clicked, bounced, unsubscribed
        sa.Column("metrics_json", postgresql.JSONB(), nullable=True),
        # Scheduling
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        # Audit fields
        sa.Column("created_by", sa.String(26), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, default=0),
        sa.Column("tenant_id", sa.String(26), nullable=True, index=True),
    )
    op.create_index("ix_marketing_campaigns_name", "marketing_campaigns", ["name"])
    op.create_index("ix_marketing_campaigns_status", "marketing_campaigns", ["status"])
    op.create_index("ix_marketing_campaigns_campaign_type", "marketing_campaigns", ["campaign_type"])
    op.create_index("ix_marketing_campaigns_campaign_trigger", "marketing_campaigns", ["campaign_trigger"])
    op.create_index("ix_marketing_campaigns_scheduled_at", "marketing_campaigns", ["scheduled_at"])
    op.create_index("ix_marketing_campaigns_created_at", "marketing_campaigns", ["created_at"])

    # Create campaign_recipients table
    op.create_table(
        "campaign_recipients",
        sa.Column("id", sa.String(26), primary_key=True),
        sa.Column(
            "campaign_id",
            sa.String(26),
            sa.ForeignKey("marketing_campaigns.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("customer_id", sa.String(26), nullable=False),
        sa.Column("channel", sa.String(20), nullable=False),  # email, sms, push
        sa.Column("status", recipient_status_enum, nullable=False, server_default="pending"),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("clicked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failed_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, default=0),
        sa.Column("tenant_id", sa.String(26), nullable=True, index=True),
    )
    op.create_index("ix_campaign_recipients_campaign_id", "campaign_recipients", ["campaign_id"])
    op.create_index("ix_campaign_recipients_customer_id", "campaign_recipients", ["customer_id"])
    op.create_index("ix_campaign_recipients_status", "campaign_recipients", ["status"])
    # Unique constraint to prevent duplicate recipients
    op.create_unique_constraint(
        "uq_campaign_recipient_customer_channel",
        "campaign_recipients",
        ["campaign_id", "customer_id", "channel"],
    )

    # Create customer_feedback table
    op.create_table(
        "customer_feedback",
        sa.Column("id", sa.String(26), primary_key=True),
        sa.Column("customer_id", sa.String(26), nullable=False),
        sa.Column("feedback_type", feedback_type_enum, nullable=False),
        sa.Column("subject", sa.String(255), nullable=True),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("rating", sa.Integer(), nullable=True),  # 1-5 star rating
        sa.Column("status", feedback_status_enum, nullable=False, server_default="pending"),
        sa.Column("sentiment", feedback_sentiment_enum, nullable=True),
        # Reference to related entities (order, product, etc.)
        sa.Column("reference_type", sa.String(50), nullable=True),
        sa.Column("reference_id", sa.String(26), nullable=True),
        # Response from staff
        sa.Column("response", sa.Text(), nullable=True),
        sa.Column("responded_by", sa.String(26), nullable=True),
        sa.Column("responded_at", sa.DateTime(timezone=True), nullable=True),
        # Resolution
        sa.Column("resolved_by", sa.String(26), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolution_notes", sa.Text(), nullable=True),
        # Visibility
        sa.Column("is_public", sa.Boolean(), nullable=False, default=False),
        sa.Column("is_featured", sa.Boolean(), nullable=False, default=False),
        # Audit fields
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, default=0),
        sa.Column("tenant_id", sa.String(26), nullable=True, index=True),
    )
    op.create_index("ix_customer_feedback_customer_id", "customer_feedback", ["customer_id"])
    op.create_index("ix_customer_feedback_feedback_type", "customer_feedback", ["feedback_type"])
    op.create_index("ix_customer_feedback_status", "customer_feedback", ["status"])
    op.create_index("ix_customer_feedback_rating", "customer_feedback", ["rating"])
    op.create_index("ix_customer_feedback_sentiment", "customer_feedback", ["sentiment"])
    op.create_index("ix_customer_feedback_reference", "customer_feedback", ["reference_type", "reference_id"])
    op.create_index("ix_customer_feedback_is_public", "customer_feedback", ["is_public"])
    op.create_index("ix_customer_feedback_created_at", "customer_feedback", ["created_at"])


def downgrade() -> None:
    # Drop tables
    op.drop_table("customer_feedback")
    op.drop_table("campaign_recipients")
    op.drop_table("marketing_campaigns")

    # Drop enum types
    op.execute("DROP TYPE IF EXISTS feedback_sentiment")
    op.execute("DROP TYPE IF EXISTS feedback_status")
    op.execute("DROP TYPE IF EXISTS feedback_type")
    op.execute("DROP TYPE IF EXISTS recipient_status")
    op.execute("DROP TYPE IF EXISTS campaign_trigger")
    op.execute("DROP TYPE IF EXISTS campaign_status")
    op.execute("DROP TYPE IF EXISTS campaign_type")
