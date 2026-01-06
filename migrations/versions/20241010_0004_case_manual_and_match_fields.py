"""add manual and match metadata to cases

Revision ID: 20241010_0004
Revises: 20240924_0003
Create Date: 2024-10-10
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20241010_0004"
down_revision = "20240924_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("cases", sa.Column("matched_case_id", sa.Integer(), nullable=True))
    op.add_column("cases", sa.Column("manual_path", sa.String(), nullable=True))
    op.add_column("cases", sa.Column("manual_meta", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("cases", "manual_meta")
    op.drop_column("cases", "manual_path")
    op.drop_column("cases", "matched_case_id")
