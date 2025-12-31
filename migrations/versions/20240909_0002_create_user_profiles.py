"""create user_profiles table

Revision ID: 20240909_0002
Revises: 20240827_0001
Create Date: 2024-09-09
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20240909_0002"
down_revision = "20240827_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_profiles",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("uid", sa.String(), nullable=False, unique=True),
        sa.Column("public_name", sa.String(), nullable=True, unique=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_user_profiles_id", "user_profiles", ["id"], unique=False)
    op.create_index("ix_user_profiles_uid", "user_profiles", ["uid"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_user_profiles_uid", table_name="user_profiles")
    op.drop_index("ix_user_profiles_id", table_name="user_profiles")
    op.drop_table("user_profiles")
