"""increase_phone_column_for_encryption

Revision ID: m7n8o9p0q1r2
Revises: l6m7n8o9p0q1
Create Date: 2024-01-17 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'm7n8o9p0q1r2'
down_revision: Union[str, None] = 'l6m7n8o9p0q1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Increase phone column size to support encrypted PII data."""
    # Encrypted data is longer than plain text
    op.alter_column(
        'customers',
        'phone',
        type_=sa.String(500),
        existing_type=sa.String(32),
        existing_nullable=True,
    )


def downgrade() -> None:
    """Revert phone column size (may truncate encrypted data)."""
    op.alter_column(
        'customers',
        'phone',
        type_=sa.String(32),
        existing_type=sa.String(500),
        existing_nullable=True,
    )
