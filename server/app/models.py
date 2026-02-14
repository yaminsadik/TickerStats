"""Database models for user data and saved analyses."""
from datetime import datetime
from sqlalchemy import (
    Column, String, DateTime, ForeignKey, JSON, Text, Integer, Boolean, Float,
    Index, UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from app.core.database import Base


class User(Base):
    """User model linked to Auth0 identity."""
    __tablename__ = "users"

    auth0_user_id = Column(String(255), primary_key=True, index=True)  # e.g., "auth0|123456"
    email = Column(String(255), unique=True, nullable=True, index=True)
    name = Column(String(255), nullable=True)
    picture = Column(Text, nullable=True)  # Avatar URL from Auth0

    # Subscription
    subscription_tier = Column(String(20), nullable=False, default="free")  # "free", "pro", "enterprise"
    stripe_customer_id = Column(String(255), nullable=True, unique=True)
    stripe_subscription_id = Column(String(255), nullable=True)
    subscription_expires_at = Column(DateTime, nullable=True)

    # Admin flag
    is_admin = Column(Boolean, nullable=False, default=False)

    # Monthly usage limits
    usage_month_start = Column(DateTime, nullable=True)
    deck_count_month = Column(Integer, nullable=False, default=0)
    compare_count_month = Column(Integer, nullable=False, default=0)
    last_compare_hash = Column(String(64), nullable=True)
    last_compare_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    watchlists = relationship("Watchlist", back_populates="user", cascade="all, delete-orphan")
    saved_analyses = relationship("SavedAnalysis", back_populates="user", cascade="all, delete-orphan")
    decks = relationship("Deck", back_populates="user", cascade="all, delete-orphan")

    @property
    def is_paid(self) -> bool:
        """Check if user has an active paid subscription."""
        if not self.subscription_tier or self.subscription_tier == "free":
            return False
        if self.subscription_tier not in {"pro", "enterprise"}:
            return False
        if self.subscription_expires_at and self.subscription_expires_at < datetime.utcnow():
            return False
        return True


class Watchlist(Base):
    """User's watchlist with custom notes."""
    __tablename__ = "watchlists"

    __table_args__ = (
        UniqueConstraint("user_id", "ticker", name="uq_watchlist_user_ticker"),
        Index("ix_watchlist_user_ticker", "user_id", "ticker"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(255), ForeignKey("users.auth0_user_id", ondelete="CASCADE"), nullable=False)
    ticker = Column(String(20), nullable=False)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    user = relationship("User", back_populates="watchlists")

    def __repr__(self):
        return f"<Watchlist(user={self.user_id}, ticker={self.ticker})>"


class SavedAnalysis(Base):
    """Saved relative table analysis configurations."""
    __tablename__ = "saved_analyses"

    __table_args__ = (
        Index("ix_saved_analyses_user_created", "user_id", "created_at"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(255), ForeignKey("users.auth0_user_id", ondelete="CASCADE"), nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)

    # Analysis configuration stored as JSON
    symbols = Column(JSON, nullable=False)  # List of ticker symbols
    snapshot_fields = Column(JSON, nullable=True)  # List of field names
    perf_periods = Column(JSON, nullable=True)  # List of performance periods
    include_dcf = Column(Boolean, default=False)
    snapshot_data = Column(JSON, nullable=True)  # Full table snapshot (RelativeTableResponse)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    user = relationship("User", back_populates="saved_analyses")

    def __repr__(self):
        return f"<SavedAnalysis(id={self.id}, name={self.name})>"


class Deck(Base):
    """Generated investment deck with AI-generated content."""
    __tablename__ = "decks"

    __table_args__ = (
        Index("ix_decks_user_created", "user_id", "created_at"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(255), ForeignKey("users.auth0_user_id", ondelete="CASCADE"), nullable=False)
    ticker = Column(String(20), nullable=False, index=True)
    title = Column(String(500), nullable=False)

    # Deck content stored as JSON (matches DeckResponse schema)
    content = Column(JSON, nullable=False)

    # Metadata
    llm_provider = Column(String(50), nullable=True)  # "openai" or "gemini"
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    user = relationship("User", back_populates="decks")

    def __repr__(self):
        return f"<Deck(id={self.id}, ticker={self.ticker}, title={self.title})>"


class LLMUsageLog(Base):
    """Per-call LLM usage ledger for cost tracking and budget-aware routing."""
    __tablename__ = "llm_usage_log"

    __table_args__ = (
        Index("ix_llm_usage_user_created", "user_id", "created_at"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(
        String(255),
        ForeignKey("users.auth0_user_id", ondelete="CASCADE"),
        nullable=False,
    )
    deck_id = Column(Integer, ForeignKey("decks.id", ondelete="SET NULL"), nullable=True)
    provider = Column(String(20), nullable=False)
    model = Column(String(50), nullable=False)
    thinking_enabled = Column(Boolean, nullable=False, default=False)
    input_tokens = Column(Integer, nullable=False, default=0)
    output_tokens = Column(Integer, nullable=False, default=0)
    reasoning_tokens = Column(Integer, nullable=False, default=0)
    estimated_cost_usd = Column(Float, nullable=False, default=0.0)
    latency_ms = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f"<LLMUsageLog(id={self.id}, model={self.model}, cost=${self.estimated_cost_usd:.4f})>"


class AdminAuditLog(Base):
    """Audit trail for admin actions (tier changes, admin toggles, etc.)."""
    __tablename__ = "admin_audit_log"

    __table_args__ = (
        Index("ix_audit_admin_created", "admin_user_id", "created_at"),
        Index("ix_audit_target_created", "target_user_id", "created_at"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    admin_user_id = Column(
        String(255),
        ForeignKey("users.auth0_user_id"),
        nullable=False,
    )
    target_user_id = Column(String(255), nullable=False)
    action = Column(String(50), nullable=False)  # "update_tier", "toggle_admin", "update_expiry"
    old_value = Column(JSONB, nullable=True)
    new_value = Column(JSONB, nullable=True)
    request_id = Column(String(64), nullable=True)  # correlate with structured logs
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f"<AdminAuditLog(id={self.id}, action={self.action}, target={self.target_user_id})>"
