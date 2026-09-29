"""Database models.

Seven tables, all keyed back to ``users``:

- users            one row per Auth0 identity: plan, monthly counters, credit balances
- watchlists       tickers a user follows (unique per user)
- saved_analyses   a saved comparison: its inputs plus a JSONB snapshot of the table
- decks            a generated pitch deck (JSONB) and when its export was unlocked
- purchases        one row per paid Stripe checkout; the unique session id makes
                   webhook retries harmless
- llm_usage_log    append-only ledger of LLM calls and their cost
- admin_audit_log  append-only record of admin changes

Conventions: timestamps are TIMESTAMPTZ in UTC with a database default of now(),
JSON is JSONB, money is NUMERIC, and every index serves a real query.
Schema changes go through Alembic migrations; ``alembic check`` verifies these
models match the migrated database.
"""
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean, CheckConstraint, Column, DateTime, ForeignKey, Index, Integer,
    Numeric, String, Text, UniqueConstraint, false, func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from app.core.database import Base

PLAN_TIERS = ("free", "pro", "enterprise")


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def created_at_column() -> Column:
    return Column(DateTime(timezone=True), nullable=False, server_default=func.now())


def counter_column() -> Column:
    return Column(Integer, nullable=False, default=0, server_default="0")


class User(Base):
    """A user, identified by their Auth0 subject (e.g. "google-oauth2|123")."""
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(
            "subscription_tier IN ('free', 'pro', 'enterprise')",
            name="ck_users_subscription_tier",
        ),
        CheckConstraint(
            "deck_count_month >= 0 AND compare_count_month >= 0"
            " AND extra_deck_credits >= 0 AND extra_compare_credits >= 0"
            " AND deck_export_credits >= 0",
            name="ck_users_counters_non_negative",
        ),
    )

    auth0_user_id = Column(String(255), primary_key=True)
    # Not unique: one person can sign in with Google and with a password, and
    # Auth0 treats those as two identities that share an email.
    email = Column(String(255), nullable=True, index=True)
    name = Column(String(255), nullable=True)
    picture = Column(Text, nullable=True)

    # Plan (kept in sync by Stripe webhooks)
    subscription_tier = Column(String(20), nullable=False, default="free", server_default="free")
    stripe_customer_id = Column(String(255), nullable=True, unique=True)
    stripe_subscription_id = Column(String(255), nullable=True)
    subscription_expires_at = Column(DateTime(timezone=True), nullable=True)
    is_admin = Column(Boolean, nullable=False, default=False, server_default=false())

    # Monthly usage. Counters reset lazily on the first request of a new month.
    usage_month_start = Column(DateTime(timezone=True), nullable=True)
    deck_count_month = counter_column()
    compare_count_month = counter_column()
    extra_deck_credits = counter_column()      # from usage packs, expire at month end
    extra_compare_credits = counter_column()   # from usage packs, expire at month end
    deck_export_credits = counter_column()     # from deck export purchases, never expire
    # Re-running the same comparison within 15 minutes is not counted twice.
    last_compare_hash = Column(String(64), nullable=True)
    last_compare_at = Column(DateTime(timezone=True), nullable=True)

    created_at = created_at_column()
    updated_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    watchlists = relationship("Watchlist", back_populates="user", cascade="all, delete-orphan")
    saved_analyses = relationship("SavedAnalysis", back_populates="user", cascade="all, delete-orphan")
    decks = relationship("Deck", back_populates="user", cascade="all, delete-orphan")
    purchases = relationship("Purchase", back_populates="user", cascade="all, delete-orphan")

    @property
    def is_paid(self) -> bool:
        """True while a pro/enterprise subscription is active."""
        if self.subscription_tier not in ("pro", "enterprise"):
            return False
        return self.subscription_expires_at is None or self.subscription_expires_at > utcnow()


class Watchlist(Base):
    """A ticker on a user's watchlist, with optional notes."""
    __tablename__ = "watchlists"
    __table_args__ = (
        # Also serves "list this user's watchlist" (user_id is the leading column).
        UniqueConstraint("user_id", "ticker", name="uq_watchlist_user_ticker"),
    )

    id = Column(Integer, primary_key=True)
    user_id = Column(String(255), ForeignKey("users.auth0_user_id", ondelete="CASCADE"), nullable=False)
    ticker = Column(String(20), nullable=False)
    notes = Column(Text, nullable=True)
    created_at = created_at_column()

    user = relationship("User", back_populates="watchlists")


class SavedAnalysis(Base):
    """A saved comparison: what was asked for, plus the table as it looked."""
    __tablename__ = "saved_analyses"
    __table_args__ = (
        Index("ix_saved_analyses_user_created", "user_id", "created_at"),
    )

    id = Column(Integer, primary_key=True)
    user_id = Column(String(255), ForeignKey("users.auth0_user_id", ondelete="CASCADE"), nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)

    symbols = Column(JSONB, nullable=False)          # ["AAPL", "MSFT"]
    snapshot_fields = Column(JSONB, nullable=True)   # ["marketCap", "forwardPE"]
    perf_periods = Column(JSONB, nullable=True)      # ["1y"]
    include_dcf = Column(Boolean, nullable=False, default=False, server_default=false())
    snapshot_data = Column(JSONB, nullable=True)     # full RelativeTableResponse

    created_at = created_at_column()
    updated_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    user = relationship("User", back_populates="saved_analyses")


class Deck(Base):
    """A generated pitch deck. Sections vary by request, so content is JSONB."""
    __tablename__ = "decks"
    __table_args__ = (
        Index("ix_decks_user_created", "user_id", "created_at"),
    )

    id = Column(Integer, primary_key=True)
    user_id = Column(String(255), ForeignKey("users.auth0_user_id", ondelete="CASCADE"), nullable=False)
    ticker = Column(String(20), nullable=False)
    title = Column(String(500), nullable=False)
    content = Column(JSONB, nullable=False)
    llm_provider = Column(String(50), nullable=True)
    export_unlocked_at = Column(DateTime(timezone=True), nullable=True)  # set when a credit is spent
    created_at = created_at_column()

    user = relationship("User", back_populates="decks")


class Purchase(Base):
    """One completed Stripe checkout for a one-time product.

    Stripe delivers webhooks at least once. Inserting this row is the first
    step of granting credits, and the unique checkout session id means a
    repeated delivery inserts nothing and grants nothing.
    """
    __tablename__ = "purchases"
    __table_args__ = (
        CheckConstraint("product IN ('usage_pack', 'deck_export')", name="ck_purchases_product"),
        Index("ix_purchases_user_created", "user_id", "created_at"),
    )

    id = Column(Integer, primary_key=True)
    user_id = Column(String(255), ForeignKey("users.auth0_user_id", ondelete="CASCADE"), nullable=False)
    stripe_checkout_session_id = Column(String(255), nullable=False, unique=True)
    product = Column(String(20), nullable=False)
    compare_credits_granted = counter_column()
    deck_credits_granted = counter_column()
    export_credits_granted = counter_column()
    created_at = created_at_column()

    user = relationship("User", back_populates="purchases")


class LLMUsageLog(Base):
    """One LLM call: tokens, latency and estimated cost."""
    __tablename__ = "llm_usage_log"
    __table_args__ = (
        Index("ix_llm_usage_user_created", "user_id", "created_at"),
    )

    id = Column(Integer, primary_key=True)
    user_id = Column(String(255), ForeignKey("users.auth0_user_id", ondelete="CASCADE"), nullable=False)
    provider = Column(String(20), nullable=False)
    model = Column(String(50), nullable=False)
    thinking_enabled = Column(Boolean, nullable=False, default=False, server_default=false())
    input_tokens = counter_column()
    output_tokens = counter_column()
    reasoning_tokens = counter_column()
    estimated_cost_usd = Column(Numeric(12, 6), nullable=False, default=0, server_default="0")
    latency_ms = counter_column()
    created_at = created_at_column()


class AdminAuditLog(Base):
    """An admin action (tier change, admin toggle, expiry change).

    target_user_id has no foreign key on purpose: the audit trail must
    outlive the user it describes.
    """
    __tablename__ = "admin_audit_log"
    __table_args__ = (
        Index("ix_audit_admin_created", "admin_user_id", "created_at"),
        Index("ix_audit_target_created", "target_user_id", "created_at"),
    )

    id = Column(Integer, primary_key=True)
    admin_user_id = Column(String(255), ForeignKey("users.auth0_user_id"), nullable=False)
    target_user_id = Column(String(255), nullable=False)
    action = Column(String(50), nullable=False)
    old_value = Column(JSONB, nullable=True)
    new_value = Column(JSONB, nullable=True)
    request_id = Column(String(64), nullable=True)
    created_at = created_at_column()
