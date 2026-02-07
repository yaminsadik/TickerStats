"""initial user tables with constraints

Revision ID: 0001
Revises:
Create Date: 2026-02-06

Creates tables: users, watchlists, saved_analyses, decks
Adds unique constraints and composite indexes for user-scoped queries.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- users ---
    op.create_table(
        "users",
        sa.Column("auth0_user_id", sa.String(255), primary_key=True),
        sa.Column("email", sa.String(255), unique=True, nullable=True),
        sa.Column("name", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_users_auth0_user_id", "users", ["auth0_user_id"])
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    # --- watchlists ---
    op.create_table(
        "watchlists",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "user_id",
            sa.String(255),
            sa.ForeignKey("users.auth0_user_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("ticker", sa.String(20), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    # Unique constraint prevents duplicate (user, ticker) pairs
    op.create_unique_constraint("uq_watchlist_user_ticker", "watchlists", ["user_id", "ticker"])
    # Composite index for fast user-scoped lookups
    op.create_index("ix_watchlist_user_ticker", "watchlists", ["user_id", "ticker"])

    # --- saved_analyses ---
    op.create_table(
        "saved_analyses",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "user_id",
            sa.String(255),
            sa.ForeignKey("users.auth0_user_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("symbols", sa.JSON(), nullable=False),
        sa.Column("snapshot_fields", sa.JSON(), nullable=True),
        sa.Column("perf_periods", sa.JSON(), nullable=True),
        sa.Column("include_dcf", sa.Boolean(), default=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_saved_analyses_user_created", "saved_analyses", ["user_id", "created_at"])

    # --- decks ---
    op.create_table(
        "decks",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "user_id",
            sa.String(255),
            sa.ForeignKey("users.auth0_user_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("ticker", sa.String(20), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("content", sa.JSON(), nullable=False),
        sa.Column("llm_provider", sa.String(50), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_decks_ticker", "decks", ["ticker"])
    op.create_index("ix_decks_user_created", "decks", ["user_id", "created_at"])


def downgrade() -> None:
    op.drop_table("decks")
    op.drop_table("saved_analyses")
    op.drop_table("watchlists")
    op.drop_table("users")
