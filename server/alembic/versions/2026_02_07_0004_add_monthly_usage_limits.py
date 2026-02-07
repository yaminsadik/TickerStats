"""add monthly usage counters to users

Revision ID: 0004
Revises: 0003
Create Date: 2026-02-07
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("usage_month_start", sa.DateTime(), nullable=True))
    op.add_column(
        "users",
        sa.Column("deck_count_month", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "users",
        sa.Column("compare_count_month", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column("users", sa.Column("last_compare_hash", sa.String(length=64), nullable=True))
    op.add_column("users", sa.Column("last_compare_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "last_compare_at")
    op.drop_column("users", "last_compare_hash")
    op.drop_column("users", "compare_count_month")
    op.drop_column("users", "deck_count_month")
    op.drop_column("users", "usage_month_start")
