"""add admin audit log table

Revision ID: 0005
Revises: 0004
Create Date: 2026-02-08
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


# revision identifiers, used by Alembic.
revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "admin_audit_log",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("admin_user_id", sa.String(length=255), nullable=False),
        sa.Column("target_user_id", sa.String(length=255), nullable=False),
        sa.Column("action", sa.String(length=50), nullable=False),
        sa.Column("old_value", JSONB(), nullable=True),
        sa.Column("new_value", JSONB(), nullable=True),
        sa.Column("request_id", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["admin_user_id"],
            ["users.auth0_user_id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_audit_admin_created",
        "admin_audit_log",
        ["admin_user_id", "created_at"],
    )
    op.create_index(
        "ix_audit_target_created",
        "admin_audit_log",
        ["target_user_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_audit_target_created", table_name="admin_audit_log")
    op.drop_index("ix_audit_admin_created", table_name="admin_audit_log")
    op.drop_table("admin_audit_log")
