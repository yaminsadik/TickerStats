"""add one-time usage pack credits

Revision ID: 0008
Revises: 0007
Create Date: 2026-05-03
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0008"
down_revision: Union[str, None] = "0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("extra_deck_credits", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "users",
        sa.Column("extra_compare_credits", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_table(
        "usage_pack_purchases",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "user_id",
            sa.String(255),
            sa.ForeignKey("users.auth0_user_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("stripe_checkout_session_id", sa.String(255), nullable=False, unique=True),
        sa.Column("compare_credits_granted", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("deck_credits_granted", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index(
        "ix_usage_pack_user_created",
        "usage_pack_purchases",
        ["user_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_usage_pack_user_created", table_name="usage_pack_purchases")
    op.drop_table("usage_pack_purchases")
    op.drop_column("users", "extra_compare_credits")
    op.drop_column("users", "extra_deck_credits")
