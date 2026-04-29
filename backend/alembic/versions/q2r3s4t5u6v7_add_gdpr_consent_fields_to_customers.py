"""add_gdpr_consent_fields_to_customers

Revision ID: q2r3s4t5u6v7
Revises: p1q2r3s4t5u6
Create Date: 2025-12-13

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'q2r3s4t5u6v7'
down_revision: Union[str, None] = 'p1q2r3s4t5u6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add GDPR consent management fields to customers table."""
    # GDPR consent data (JSON for flexible consent types)
    op.add_column('customers', sa.Column(
        'consent_data',
        sa.JSON(),
        nullable=True,
        comment='GDPR consent preferences: {type: {granted, updated_at}}'
    ))
    
    # When consent was last updated
    op.add_column('customers', sa.Column(
        'consent_updated_at',
        sa.DateTime(timezone=True),
        nullable=True,
        comment='Timestamp of last consent update'
    ))
    
    # Right to erasure (GDPR Article 17)
    op.add_column('customers', sa.Column(
        'erasure_requested_at',
        sa.DateTime(timezone=True),
        nullable=True,
        comment='When data erasure was requested'
    ))
    
    op.add_column('customers', sa.Column(
        'erasure_reason',
        sa.String(500),
        nullable=True,
        comment='Reason for erasure request'
    ))
    
    # Index for finding customers with pending erasure requests
    op.create_index(
        'ix_customers_erasure_requested',
        'customers',
        ['erasure_requested_at'],
        postgresql_where=sa.text('erasure_requested_at IS NOT NULL')
    )


def downgrade() -> None:
    """Remove GDPR consent fields from customers table."""
    op.drop_index('ix_customers_erasure_requested', table_name='customers')
    op.drop_column('customers', 'erasure_reason')
    op.drop_column('customers', 'erasure_requested_at')
    op.drop_column('customers', 'consent_updated_at')
    op.drop_column('customers', 'consent_data')
