"""merge multiple heads

Revision ID: 4ae8e28625e1
Revises: e7f9a3b2c4d6, i3j4k5l6m7n8
Create Date: 2025-12-12 18:59:47.063100

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4ae8e28625e1'
down_revision: Union[str, None] = ('e7f9a3b2c4d6', 'i3j4k5l6m7n8')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
