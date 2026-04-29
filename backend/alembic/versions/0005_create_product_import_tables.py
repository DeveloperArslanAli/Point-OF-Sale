from __future__ import annotations

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "0005_create_product_import_tables"
down_revision = "0004_create_categories_table"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "product_import_jobs",
        sa.Column("id", sa.String(length=26), primary_key=True),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("total_rows", sa.Integer(), nullable=False),
    sa.Column("processed_rows", sa.Integer(), nullable=False, server_default=sa.text("0")),
    sa.Column("error_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
    sa.Column("errors", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_product_import_jobs_status", "product_import_jobs", ["status"])

    op.create_table(
        "product_import_job_items",
        sa.Column("id", sa.String(length=26), primary_key=True),
        sa.Column(
            "job_id",
            sa.String(length=26),
            sa.ForeignKey("product_import_jobs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("row_number", sa.Integer(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("error_message", sa.String(length=512), nullable=True),
    )
    op.create_index("ix_product_import_job_items_job_id", "product_import_job_items", ["job_id"])
    op.create_index("ix_product_import_job_items_status", "product_import_job_items", ["status"])


def downgrade() -> None:
    op.drop_index("ix_product_import_job_items_status", table_name="product_import_job_items")
    op.drop_index("ix_product_import_job_items_job_id", table_name="product_import_job_items")
    op.drop_table("product_import_job_items")
    op.drop_index("ix_product_import_jobs_status", table_name="product_import_jobs")
    op.drop_table("product_import_jobs")
