"""create case_comments table

Revision ID: 20240924_0003
Revises: 20240909_0002
Create Date: 2024-09-24
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20240924_0003"
down_revision = "20240909_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "case_comments",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("case_id", sa.Integer(), sa.ForeignKey("cases.id"), nullable=False),
        sa.Column("author_uid", sa.String(), nullable=False),
        sa.Column("author_public_name", sa.String(), nullable=True),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_case_comments_id", "case_comments", ["id"], unique=False)
    op.create_index("ix_case_comments_case_id", "case_comments", ["case_id"], unique=False)
    op.create_index(
        "ix_case_comments_author_uid", "case_comments", ["author_uid"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_case_comments_author_uid", table_name="case_comments")
    op.drop_index("ix_case_comments_case_id", table_name="case_comments")
    op.drop_index("ix_case_comments_id", table_name="case_comments")
    op.drop_table("case_comments")
