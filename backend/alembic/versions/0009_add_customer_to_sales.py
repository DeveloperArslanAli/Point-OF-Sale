from __future__ import annotations

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "0009_add_customer_to_sales"
down_revision = "0008_create_customers_table"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("sales") as batch_op:
        batch_op.add_column(sa.Column("customer_id", sa.String(length=26), nullable=True))
        batch_op.create_foreign_key(
            "fk_sales_customer_id_customers",
            "customers",
            ["customer_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_index("ix_sales_customer_id", ["customer_id"])


def downgrade() -> None:
    with op.batch_alter_table("sales") as batch_op:
        batch_op.drop_index("ix_sales_customer_id")
        batch_op.drop_constraint("fk_sales_customer_id_customers", type_="foreignkey")
        batch_op.drop_column("customer_id")
