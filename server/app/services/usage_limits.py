"""Monthly plan limits.

Free users get a few compares and decks per month; usage packs add more.
Limits are enforced by *reserving* a unit before the expensive work:

    lock the user's row -> reset counters if a new month started
    -> check the limit -> increment -> commit (releases the lock)

The row lock (SELECT ... FOR UPDATE) makes two simultaneous requests take
turns, so a user at 4/5 cannot get two requests through. The lock is held
for one short transaction, never while calling Yahoo Finance or an LLM.
If deck generation then fails, the reservation is refunded.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import PLAN_TIERS, LLMUsageLog, User, utcnow

FREE_COMPARE_LIMIT = 5
FREE_DECK_LIMIT = 1
PRO_DECK_LIMIT = 100
USAGE_PACK_COMPARE_CREDITS = 10
USAGE_PACK_DECK_CREDITS = 2
FAIRNESS_WINDOW = timedelta(minutes=15)
DAILY_THINKING_LIMIT = 20


def get_plan_tier(user: User) -> str:
    if user.is_admin:
        return "enterprise"
    return user.subscription_tier if user.subscription_tier in PLAN_TIERS else "free"


def get_user_compare_limit(user: User) -> Optional[int]:
    """Compares allowed this month, or None for unlimited."""
    if get_plan_tier(user) == "free":
        return FREE_COMPARE_LIMIT + user.extra_compare_credits
    return None


def get_user_deck_limit(user: User) -> Optional[int]:
    """Decks allowed this month, or None for unlimited."""
    tier = get_plan_tier(user)
    if tier == "free":
        return FREE_DECK_LIMIT + user.extra_deck_credits
    if tier == "pro":
        return PRO_DECK_LIMIT + user.extra_deck_credits
    return None


def get_daily_thinking_limit(plan_tier: str) -> Optional[int]:
    """Daily cap on thinking-mode LLM calls, or None for unlimited."""
    return None if plan_tier == "enterprise" else DAILY_THINKING_LIMIT


def month_start(now: datetime) -> datetime:
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def reset_monthly_usage(user: User, now: datetime) -> None:
    """Start a new month lazily: the first request after the 1st resets counters.

    Usage-pack credits are monthly, so they reset too.
    """
    if user.usage_month_start is None or user.usage_month_start < month_start(now):
        user.usage_month_start = month_start(now)
        user.deck_count_month = 0
        user.compare_count_month = 0
        user.extra_deck_credits = 0
        user.extra_compare_credits = 0
        user.last_compare_hash = None
        user.last_compare_at = None


def compute_compare_hash(
    symbols: list[str],
    fields: Optional[list[str]],
    perf_metrics: Optional[list[str]],
    perf_period: Optional[str],
    dcf: bool,
) -> str:
    """Order-insensitive fingerprint of a comparison request."""
    payload = {
        "symbols": sorted({s.upper().strip() for s in symbols}),
        "fields": sorted(set(fields or [])),
        "perf": sorted(set(perf_metrics or [])),
        "perfPeriod": perf_period or "",
        "dcf": bool(dcf),
    }
    raw = json.dumps(payload, separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


async def lock_user(db: AsyncSession, user_id: str) -> Optional[User]:
    """SELECT ... FOR UPDATE, re-reading the row even if the session already has it.

    Without populate_existing the ORM would hand back the copy it loaded at
    the start of the request, and the check would run on stale counters.
    """
    result = await db.execute(
        select(User)
        .where(User.auth0_user_id == user_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    return result.scalar_one_or_none()


async def reserve_compare(
    db: AsyncSession, user_id: str, compare_hash: str
) -> tuple[bool, Optional[int]]:
    """Count one compare against the monthly limit. Returns (allowed, limit).

    The caller commits right away to release the row lock.
    """
    now = utcnow()
    user = await lock_user(db, user_id)
    if user is None:
        return False, None
    reset_monthly_usage(user, now)
    limit = get_user_compare_limit(user)
    if limit is None:
        return True, None

    is_repeat = (
        user.last_compare_hash == compare_hash
        and user.last_compare_at is not None
        and now - user.last_compare_at <= FAIRNESS_WINDOW
    )
    if is_repeat:
        return True, limit
    if user.compare_count_month >= limit:
        return False, limit

    user.compare_count_month += 1
    user.last_compare_hash = compare_hash
    user.last_compare_at = now
    return True, limit


async def reserve_deck(db: AsyncSession, user_id: str) -> tuple[bool, Optional[int]]:
    """Count one deck against the monthly limit. Returns (allowed, limit)."""
    user = await lock_user(db, user_id)
    if user is None:
        return False, None
    reset_monthly_usage(user, utcnow())
    limit = get_user_deck_limit(user)
    if limit is None:
        return True, None
    if user.deck_count_month >= limit:
        return False, limit
    user.deck_count_month += 1
    return True, limit


async def refund_deck(db: AsyncSession, user_id: str) -> None:
    """Give back a reserved deck after generation failed."""
    await db.execute(
        update(User)
        .where(User.auth0_user_id == user_id, User.deck_count_month > 0)
        .values(deck_count_month=User.deck_count_month - 1)
    )


async def spend_export_credit(db: AsyncSession, user_id: str) -> Optional[int]:
    """Atomically take one deck export credit. Returns the new balance, or None if none left.

    One conditional UPDATE: the database checks and decrements in a single
    step, so two requests can never both spend the last credit.
    """
    result = await db.execute(
        update(User)
        .where(User.auth0_user_id == user_id, User.deck_export_credits > 0)
        .values(deck_export_credits=User.deck_export_credits - 1)
        .returning(User.deck_export_credits)
    )
    return result.scalar_one_or_none()


async def get_daily_thinking_uses(db: AsyncSession, user_id: str) -> int:
    """Thinking-mode LLM calls made today (UTC)."""
    today = utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    result = await db.execute(
        select(func.count(LLMUsageLog.id)).where(
            LLMUsageLog.user_id == user_id,
            LLMUsageLog.thinking_enabled.is_(True),
            LLMUsageLog.created_at >= today,
        )
    )
    return result.scalar() or 0


async def get_monthly_model_cost(db: AsyncSession, user_id: str) -> float:
    """Estimated LLM spend this calendar month, in USD."""
    result = await db.execute(
        select(func.coalesce(func.sum(LLMUsageLog.estimated_cost_usd), 0)).where(
            LLMUsageLog.user_id == user_id,
            LLMUsageLog.created_at >= month_start(utcnow()),
        )
    )
    return float(result.scalar())
