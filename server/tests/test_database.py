"""Database tests against a real PostgreSQL.

Run with a throwaway database (its name must contain "test"):

    TEST_DATABASE_URL=postgresql://postgres:postgres@localhost:5432/tickerstats_test pytest tests/test_database.py

The schema is built by running the real Alembic migrations, then
``alembic check`` confirms the models match it. The concurrency tests fire
several requests at once for the same user to prove the limits hold.
"""
import asyncio
import os
import subprocess
import sys
from datetime import timedelta
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy import make_url, select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.auth import upsert_user_from_token
from app.deck.services.stripe_service import StripeService
from app.models import Deck, Purchase, User, utcnow
from app.services.usage_limits import (
    FREE_COMPARE_LIMIT,
    month_start,
    refund_deck,
    reserve_compare,
    reserve_deck,
    spend_export_credit,
)

SERVER_DIR = Path(__file__).resolve().parents[1]
TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL", "")

pytestmark = pytest.mark.skipif(not TEST_DATABASE_URL, reason="set TEST_DATABASE_URL to run database tests")


def _run_alembic(*args: str) -> str:
    result = subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=SERVER_DIR,
        env={**os.environ, "DATABASE_URL": TEST_DATABASE_URL},
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    return result.stdout + result.stderr


@pytest.fixture(scope="module")
def migrated_database():
    """Rebuild the schema from zero with the real migrations."""
    import psycopg

    assert "test" in make_url(TEST_DATABASE_URL).database, "refusing to wipe a non-test database"
    with psycopg.connect(TEST_DATABASE_URL, autocommit=True) as conn:
        conn.execute("DROP SCHEMA public CASCADE")
        conn.execute("CREATE SCHEMA public")
    _run_alembic("upgrade", "head")
    return TEST_DATABASE_URL


@pytest_asyncio.fixture
async def sessions(migrated_database):
    """A session factory on a clean database."""
    _, _, rest = migrated_database.partition("://")
    engine = create_async_engine(f"postgresql+psycopg://{rest}", pool_size=10)
    async with engine.begin() as conn:
        await conn.execute(text(
            "TRUNCATE users, watchlists, saved_analyses, decks, purchases, "
            "llm_usage_log, admin_audit_log RESTART IDENTITY CASCADE"
        ))
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


async def _add_user(sessions, user_id="auth0|alice", **fields) -> None:
    async with sessions() as db:
        db.add(User(auth0_user_id=user_id, usage_month_start=month_start(utcnow()), **fields))
        await db.commit()


async def _get_user(sessions, user_id="auth0|alice") -> User:
    async with sessions() as db:
        return await db.get(User, user_id)


def test_models_match_migrations(migrated_database):
    assert "No new upgrade operations detected" in _run_alembic("check")


@pytest.mark.asyncio
async def test_concurrent_compares_cannot_exceed_limit(sessions):
    await _add_user(sessions, compare_count_month=FREE_COMPARE_LIMIT - 1)
    all_authenticated = asyncio.Barrier(5)

    async def one_request(i: int) -> bool:
        async with sessions() as db:
            # Hold the user loaded during auth, as the real route does (the
            # identity map is weak, so an unreferenced object would simply be
            # reloaded), and let every request load it before any checks the limit.
            current_user = await db.get(User, "auth0|alice")
            await all_authenticated.wait()
            allowed, _ = await reserve_compare(db, current_user.auth0_user_id, compare_hash=f"query-{i}")
            await db.commit()
            return allowed

    results = await asyncio.gather(*(one_request(i) for i in range(5)))

    assert results.count(True) == 1
    assert (await _get_user(sessions)).compare_count_month == FREE_COMPARE_LIMIT


@pytest.mark.asyncio
async def test_repeating_a_compare_within_window_is_free(sessions):
    await _add_user(sessions)
    for _ in range(3):
        async with sessions() as db:
            assert (await reserve_compare(db, "auth0|alice", "same-query"))[0]
            await db.commit()
    assert (await _get_user(sessions)).compare_count_month == 1


@pytest.mark.asyncio
async def test_new_month_resets_counters_and_pack_credits(sessions):
    last_month = month_start(month_start(utcnow()) - timedelta(days=1))
    await _add_user(sessions, compare_count_month=5, extra_compare_credits=10)
    async with sessions() as db:
        await db.execute(update(User).values(usage_month_start=last_month))
        await db.commit()

    async with sessions() as db:
        allowed, limit = await reserve_compare(db, "auth0|alice", "q")
        await db.commit()

    user = await _get_user(sessions)
    assert allowed and limit == FREE_COMPARE_LIMIT
    assert user.compare_count_month == 1 and user.extra_compare_credits == 0


@pytest.mark.asyncio
async def test_deck_reservation_and_refund(sessions):
    await _add_user(sessions)  # free plan: one deck per month
    async with sessions() as db:
        assert (await reserve_deck(db, "auth0|alice"))[0]
        await db.commit()
    async with sessions() as db:
        assert not (await reserve_deck(db, "auth0|alice"))[0]
        await refund_deck(db, "auth0|alice")
        await db.commit()
    assert (await _get_user(sessions)).deck_count_month == 0


@pytest.mark.asyncio
async def test_last_export_credit_can_only_be_spent_once(sessions):
    await _add_user(sessions, deck_export_credits=1)

    async def spend():
        async with sessions() as db:
            remaining = await spend_export_credit(db, "auth0|alice")
            await db.commit()
            return remaining

    results = await asyncio.gather(*(spend() for _ in range(5)))

    assert results.count(0) == 1 and results.count(None) == 4
    assert (await _get_user(sessions)).deck_export_credits == 0


@pytest.mark.asyncio
async def test_database_rejects_negative_credits(sessions):
    await _add_user(sessions)
    async with sessions() as db:
        with pytest.raises(IntegrityError, match="ck_users_counters_non_negative"):
            await db.execute(update(User).values(deck_export_credits=-1))


@pytest.mark.asyncio
async def test_simultaneous_first_logins_create_one_user(sessions):
    async def login():
        async with sessions() as db:
            user = await upsert_user_from_token(db, "auth0|new", {"email": "new@example.com"})
            await db.commit()
            return user.auth0_user_id

    assert await asyncio.gather(*(login() for _ in range(5))) == ["auth0|new"] * 5
    async with sessions() as db:
        assert len((await db.execute(select(User))).scalars().all()) == 1


@pytest.mark.asyncio
async def test_repeated_stripe_webhook_grants_credits_once(sessions):
    await _add_user(sessions)
    async with sessions() as db:
        db.add(Deck(user_id="auth0|alice", ticker="AAPL", title="Apple", content={}))
        await db.commit()
    checkout = {
        "id": "cs_test_123",
        "customer": "cus_123",
        "metadata": {"auth0_user_id": "auth0|alice", "product": "deck_export", "deck_id": "1"},
    }

    for _ in range(3):  # Stripe retries deliveries
        async with sessions() as db:
            await StripeService._handle_one_time_purchase(checkout, db)
            await db.commit()

    user = await _get_user(sessions)
    async with sessions() as db:
        deck = await db.get(Deck, 1)
        purchases = (await db.execute(select(Purchase))).scalars().all()
    assert len(purchases) == 1
    assert deck.export_unlocked_at is not None
    assert user.deck_export_credits == 1  # 2 bought, 1 used to unlock deck 1
