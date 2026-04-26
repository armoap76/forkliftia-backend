"""add updated_at to case_comments

Revision ID: 20241020_0005
Revises: 20241010_0004
Create Date: 2024-10-20
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20241020_0005"
down_revision = "20241010_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "case_comments",
        sa.Column("updated_at", sa.DateTime(), nullable=True, server_default=sa.func.now()),
    )
    op.execute("UPDATE case_comments SET updated_at = created_at WHERE updated_at IS NULL")
    op.alter_column("case_comments", "updated_at", nullable=False)


def downgrade() -> None:
    op.drop_column("case_comments", "updated_at")
