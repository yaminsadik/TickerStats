"""add llm_usage_log table for per-call cost tracking

Revision ID: 0006
Revises: 0005
Create Date: 2026-02-13
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "llm_usage_log",
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
            sa.ForeignKey("decks.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("provider", sa.String(20), nullable=False),
        sa.Column("model", sa.String(50), nullable=False),
        sa.Column("thinking_enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("input_tokens", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("output_tokens", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("reasoning_tokens", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("estimated_cost_usd", sa.Float(), nullable=False, server_default=sa.text("0.0")),
        sa.Column("latency_ms", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_llm_usage_user_created", "llm_usage_log", ["user_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_llm_usage_user_created", table_name="llm_usage_log")
    op.drop_table("llm_usage_log")
