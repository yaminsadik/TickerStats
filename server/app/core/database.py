"""Database engine and session management."""
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings


engine = create_async_engine(
    settings.sqlalchemy_database_url,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)

AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    """Base class for all database models."""

    # Read database-generated values (created_at, updated_at) back with
    # RETURNING on every INSERT/UPDATE, so async code never lazy-loads them.
    __mapper_args__ = {"eager_defaults": True}


async def get_db():
    """FastAPI dependency: one session per request, committed on success."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
