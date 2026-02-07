"""Database models for user data and saved analyses."""
from datetime import datetime
from sqlalchemy import (
    Column, String, DateTime, ForeignKey, JSON, Text, Integer, Boolean,
    Index, UniqueConstraint,
)
from sqlalchemy.orm import relationship
from app.core.database import Base


class User(Base):
    """User model linked to Auth0 identity."""
    __tablename__ = "users"

    auth0_user_id = Column(String(255), primary_key=True, index=True)  # e.g., "auth0|123456"
    email = Column(String(255), unique=True, nullable=True, index=True)
    name = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    watchlists = relationship("Watchlist", back_populates="user", cascade="all, delete-orphan")
    saved_analyses = relationship("SavedAnalysis", back_populates="user", cascade="all, delete-orphan")
    decks = relationship("Deck", back_populates="user", cascade="all, delete-orphan")


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
