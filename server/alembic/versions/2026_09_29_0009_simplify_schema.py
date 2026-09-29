"""simplify schema: fewer tables, right types, real constraints

Revision ID: 0009
Revises: 0008
Create Date: 2026-09-29

- Drop four indexes that duplicated a primary key or unique constraint, and
  one that no query used.
- users.email is no longer unique (it is not the identity key).
- deck_export_unlocks becomes decks.export_unlocked_at.
- usage_pack_purchases becomes purchases and also records deck exports, so
  every credit-granting webhook is idempotent on the checkout session id.
- CHECK constraints for plan tier and non-negative counters/credits.
- TIMESTAMP -> TIMESTAMPTZ (stored values were UTC), JSON -> JSONB,
  FLOAT -> NUMERIC for money.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


revision: str = "0009"
down_revision: Union[str, None] = "0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TIMESTAMP_COLUMNS = [
    ("users", "subscription_expires_at"),
    ("users", "usage_month_start"),
    ("users", "last_compare_at"),
    ("users", "created_at"),
    ("users", "updated_at"),
    ("watchlists", "created_at"),
    ("saved_analyses", "created_at"),
    ("saved_analyses", "updated_at"),
    ("decks", "created_at"),
    ("purchases", "created_at"),
    ("llm_usage_log", "created_at"),
    ("admin_audit_log", "created_at"),
]

JSON_COLUMNS = [
    ("saved_analyses", "symbols"),
    ("saved_analyses", "snapshot_fields"),
    ("saved_analyses", "perf_periods"),
    ("saved_analyses", "snapshot_data"),
    ("decks", "content"),
]

COUNTER_COLUMNS = [
    "deck_count_month",
    "compare_count_month",
    "extra_deck_credits",
    "extra_compare_credits",
    "deck_export_credits",
]


def upgrade() -> None:
    # 1. Indexes that did nothing but slow down writes
    op.drop_index("ix_users_auth0_user_id", table_name="users")          # duplicate of users_pkey
    op.drop_index("ix_watchlist_user_ticker", table_name="watchlists")   # duplicate of uq_watchlist_user_ticker
    op.drop_index("ix_decks_ticker", table_name="decks")                  # no query filters decks by ticker

    # 2. Email is contact data, not identity: keep a lookup index, drop uniqueness
    op.drop_constraint("users_email_key", "users", type_="unique")
    op.drop_index("ix_users_email", table_name="users")
    op.create_index("ix_users_email", "users", ["email"])

    # 3. A deck export unlock is a property of one deck
    op.add_column("decks", sa.Column("export_unlocked_at", sa.DateTime(timezone=True), nullable=True))
    op.execute(
        "UPDATE decks SET export_unlocked_at = u.created_at AT TIME ZONE 'UTC' "
        "FROM deck_export_unlocks u WHERE u.deck_id = decks.id"
    )

    # 4. One purchases table for every one-time checkout
    op.rename_table("usage_pack_purchases", "purchases")
    op.execute("ALTER SEQUENCE usage_pack_purchases_id_seq RENAME TO purchases_id_seq")
    op.execute("ALTER INDEX usage_pack_purchases_pkey RENAME TO purchases_pkey")
    op.execute(
        "ALTER TABLE purchases RENAME CONSTRAINT usage_pack_purchases_stripe_checkout_session_id_key "
        "TO purchases_stripe_checkout_session_id_key"
    )
    op.execute("ALTER TABLE purchases RENAME CONSTRAINT usage_pack_purchases_user_id_fkey TO purchases_user_id_fkey")
    op.execute("ALTER INDEX ix_usage_pack_user_created RENAME TO ix_purchases_user_created")
    op.add_column("purchases", sa.Column("product", sa.String(20), nullable=False, server_default="usage_pack"))
    op.alter_column("purchases", "product", server_default=None)
    op.add_column(
        "purchases",
        sa.Column("export_credits_granted", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_check_constraint("ck_purchases_product", "purchases", "product IN ('usage_pack', 'deck_export')")
    op.execute(
        "INSERT INTO purchases (user_id, stripe_checkout_session_id, product, export_credits_granted, created_at) "
        "SELECT user_id, stripe_checkout_session_id, 'deck_export', 2, created_at "
        "FROM deck_export_unlocks WHERE stripe_checkout_session_id IS NOT NULL"
    )
    op.drop_table("deck_export_unlocks")

    # 5. Clean existing rows, then let the database enforce the rules
    op.execute("UPDATE users SET subscription_tier = lower(subscription_tier)")
    op.execute(
        "UPDATE users SET subscription_tier = 'free' "
        "WHERE subscription_tier NOT IN ('free', 'pro', 'enterprise')"
    )
    op.execute(
        "UPDATE users SET " + ", ".join(f"{c} = GREATEST({c}, 0)" for c in COUNTER_COLUMNS)
    )
    op.create_check_constraint(
        "ck_users_subscription_tier", "users", "subscription_tier IN ('free', 'pro', 'enterprise')"
    )
    op.create_check_constraint(
        "ck_users_counters_non_negative", "users", " AND ".join(f"{c} >= 0" for c in COUNTER_COLUMNS)
    )
    op.execute("UPDATE saved_analyses SET include_dcf = false WHERE include_dcf IS NULL")
    op.alter_column("saved_analyses", "include_dcf", nullable=False, server_default=sa.false())

    # 6. Types: timezone-aware timestamps, binary JSON, exact money
    for table, column in TIMESTAMP_COLUMNS:
        op.alter_column(
            table, column,
            type_=sa.DateTime(timezone=True),
            postgresql_using=f"{column} AT TIME ZONE 'UTC'",
        )
    op.alter_column("admin_audit_log", "created_at", server_default=sa.func.now())
    for table, column in JSON_COLUMNS:
        op.alter_column(table, column, type_=JSONB(), postgresql_using=f"{column}::jsonb")
    op.alter_column("llm_usage_log", "estimated_cost_usd", type_=sa.Numeric(12, 6))

    # 7. llm_usage_log.deck_id was never written
    op.drop_column("llm_usage_log", "deck_id")


def downgrade() -> None:
    # Deck-export checkout ids cannot be re-linked to decks, so they are dropped.
    op.add_column(
        "llm_usage_log",
        sa.Column("deck_id", sa.Integer(), sa.ForeignKey("decks.id", ondelete="SET NULL"), nullable=True),
    )
    op.alter_column("llm_usage_log", "estimated_cost_usd", type_=sa.Float())
    for table, column in JSON_COLUMNS:
        op.alter_column(table, column, type_=sa.JSON(), postgresql_using=f"{column}::json")
    op.alter_column("admin_audit_log", "created_at", server_default=None)
    for table, column in TIMESTAMP_COLUMNS:
        op.alter_column(
            table, column,
            type_=sa.DateTime(),
            postgresql_using=f"{column} AT TIME ZONE 'UTC'",
        )

    op.alter_column("saved_analyses", "include_dcf", nullable=True, server_default=None)
    op.drop_constraint("ck_users_counters_non_negative", "users", type_="check")
    op.drop_constraint("ck_users_subscription_tier", "users", type_="check")

    op.create_table(
        "deck_export_unlocks",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.String(255), sa.ForeignKey("users.auth0_user_id", ondelete="CASCADE"), nullable=False),
        sa.Column("deck_id", sa.Integer(), sa.ForeignKey("decks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("stripe_checkout_session_id", sa.String(255), nullable=True, unique=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "deck_id", name="uq_deck_export_unlock_user_deck"),
    )
    op.create_index("ix_deck_export_unlock_user_deck", "deck_export_unlocks", ["user_id", "deck_id"])
    op.execute(
        "INSERT INTO deck_export_unlocks (user_id, deck_id, created_at) "
        "SELECT user_id, id, export_unlocked_at AT TIME ZONE 'UTC' FROM decks "
        "WHERE export_unlocked_at IS NOT NULL"
    )
    op.drop_column("decks", "export_unlocked_at")

    op.execute("DELETE FROM purchases WHERE product <> 'usage_pack'")
    op.drop_constraint("ck_purchases_product", "purchases", type_="check")
    op.drop_column("purchases", "export_credits_granted")
    op.drop_column("purchases", "product")
    op.execute("ALTER INDEX ix_purchases_user_created RENAME TO ix_usage_pack_user_created")
    op.execute("ALTER TABLE purchases RENAME CONSTRAINT purchases_user_id_fkey TO usage_pack_purchases_user_id_fkey")
    op.execute(
        "ALTER TABLE purchases RENAME CONSTRAINT purchases_stripe_checkout_session_id_key "
        "TO usage_pack_purchases_stripe_checkout_session_id_key"
    )
    op.execute("ALTER INDEX purchases_pkey RENAME TO usage_pack_purchases_pkey")
    op.execute("ALTER SEQUENCE purchases_id_seq RENAME TO usage_pack_purchases_id_seq")
    op.rename_table("purchases", "usage_pack_purchases")

    op.drop_index("ix_users_email", table_name="users")
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_unique_constraint("users_email_key", "users", ["email"])
    op.create_index("ix_decks_ticker", "decks", ["ticker"])
    op.create_index("ix_watchlist_user_ticker", "watchlists", ["user_id", "ticker"])
    op.create_index("ix_users_auth0_user_id", "users", ["auth0_user_id"])
