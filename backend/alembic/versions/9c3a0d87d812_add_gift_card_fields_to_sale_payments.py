"""add gift card linkage to sale payments

Revision ID: 9c3a0d87d812
Revises: c03c378685db
Create Date: 2025-12-07 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "9c3a0d87d812"
down_revision: Union[str, None] = "c03c378685db"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("sale_payments", sa.Column("gift_card_id", sa.String(length=26), nullable=True))
    op.add_column("sale_payments", sa.Column("gift_card_code", sa.String(length=20), nullable=True))
    op.create_index(
        "ix_sale_payments_gift_card_id",
        "sale_payments",
        ["gift_card_id"],
        unique=False,
    )
    op.create_foreign_key(
        "fk_sale_payments_gift_card_id_gift_cards",
        "sale_payments",
        "gift_cards",
        ["gift_card_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_sale_payments_gift_card_id_gift_cards", "sale_payments", type_="foreignkey")
    op.drop_index("ix_sale_payments_gift_card_id", table_name="sale_payments")
    op.drop_column("sale_payments", "gift_card_code")
    op.drop_column("sale_payments", "gift_card_id")
