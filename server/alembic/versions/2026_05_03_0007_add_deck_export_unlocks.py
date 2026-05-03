"""add one-time deck export unlocks

Revision ID: 0007
Revises: 0006
Create Date: 2026-05-03
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0007"
down_revision: Union[str, None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("deck_export_credits", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_table(
        "deck_export_unlocks",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "user_id",
            sa.String(255),
            sa.ForeignKey("users.auth0_user_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "deck_id",
            sa.Integer(),
            sa.ForeignKey("decks.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("stripe_checkout_session_id", sa.String(255), nullable=True, unique=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "deck_id", name="uq_deck_export_unlock_user_deck"),
    )
    op.create_index(
        "ix_deck_export_unlock_user_deck",
        "deck_export_unlocks",
        ["user_id", "deck_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_deck_export_unlock_user_deck", table_name="deck_export_unlocks")
    op.drop_table("deck_export_unlocks")
    op.drop_column("users", "deck_export_credits")
