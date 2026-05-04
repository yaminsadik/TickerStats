"""Monthly usage limit helpers for free/pro tiers."""
from __future__ import annotations

from datetime import datetime, timedelta
import hashlib
import json
from typing import Optional, Tuple

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.models import LLMUsageLog, User

# Limits
FREE_COMPARE_LIMIT = 5
FREE_DECK_LIMIT = 1
PRO_DECK_LIMIT = 100
USAGE_PACK_COMPARE_CREDITS = 10
USAGE_PACK_DECK_CREDITS = 2
FAIRNESS_WINDOW_MINUTES = 15


def get_plan_tier(user: User) -> str:
    if user.is_admin:
        return "enterprise"
    tier = (user.subscription_tier or "free").lower()
    if tier not in {"free", "pro", "enterprise"}:
        return "free"
    return tier


def _clean_extra_credits(value: Optional[int]) -> int:
    return max(int(value or 0), 0)


def get_compare_limit(plan_tier: str, extra_credits: int = 0) -> Optional[int]:
    if plan_tier == "free":
        return FREE_COMPARE_LIMIT + _clean_extra_credits(extra_credits)
    return None


def get_deck_limit(plan_tier: str, extra_credits: int = 0) -> Optional[int]:
    if plan_tier == "free":
        return FREE_DECK_LIMIT + _clean_extra_credits(extra_credits)
    if plan_tier == "pro":
        return PRO_DECK_LIMIT + _clean_extra_credits(extra_credits)
    return None


def get_user_compare_limit(user: User) -> Optional[int]:
    return get_compare_limit(
        get_plan_tier(user),
        _clean_extra_credits(getattr(user, "extra_compare_credits", 0)),
    )


def get_user_deck_limit(user: User) -> Optional[int]:
    return get_deck_limit(
        get_plan_tier(user),
        _clean_extra_credits(getattr(user, "extra_deck_credits", 0)),
    )


def month_start(dt: datetime) -> datetime:
    return datetime(dt.year, dt.month, 1)


def reset_monthly_usage(user: User, now: datetime) -> bool:
    """Reset monthly counters if month has changed. Returns True if reset."""
    current_start = month_start(now)
    if not user.usage_month_start or user.usage_month_start < current_start:
        user.usage_month_start = current_start
        user.deck_count_month = 0
        user.compare_count_month = 0
        user.extra_deck_credits = 0
        user.extra_compare_credits = 0
        user.last_compare_hash = None
        user.last_compare_at = None
        return True
    return False


def compute_compare_hash(
    symbols: list[str],
    fields: Optional[list[str]],
    perf_metrics: Optional[list[str]],
    perf_period: Optional[str],
    dcf: bool,
) -> str:
    payload = {
        "symbols": sorted({s.upper().strip() for s in symbols}),
        "fields": sorted({f for f in (fields or [])}),
        "perf": sorted({p for p in (perf_metrics or [])}),
        "perfPeriod": perf_period or "",
        "dcf": bool(dcf),
    }
    raw = json.dumps(payload, separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def should_skip_compare_increment(user: User, new_hash: str, now: datetime) -> bool:
    if not user.last_compare_hash or not user.last_compare_at:
        return False
    if user.last_compare_hash != new_hash:
        return False
    return now - user.last_compare_at <= timedelta(minutes=FAIRNESS_WINDOW_MINUTES)


async def check_compare_limit_async(
    user: User,
    now: datetime,
    compare_hash: str,
) -> Tuple[bool, bool, Optional[int]]:
    """Return (allowed, should_increment, limit)."""
    reset_monthly_usage(user, now)
    limit = get_user_compare_limit(user)
    if limit is None:
        return True, False, None
    if should_skip_compare_increment(user, compare_hash, now):
        return True, False, limit
    if user.compare_count_month >= limit:
        return False, False, limit
    return True, True, limit


async def apply_compare_increment_async(user: User, now: datetime, compare_hash: str) -> None:
    user.compare_count_month = (user.compare_count_month or 0) + 1
    user.last_compare_hash = compare_hash
    user.last_compare_at = now


def check_deck_limit_sync(user: User, now: datetime) -> Tuple[bool, Optional[int]]:
    """Return (allowed, limit)."""
    reset_monthly_usage(user, now)
    limit = get_user_deck_limit(user)
    if limit is None:
        return True, None
    if user.deck_count_month >= limit:
        return False, limit
    return True, limit


def increment_deck_usage_sync(user: User, now: datetime) -> None:
    reset_monthly_usage(user, now)
    user.deck_count_month = (user.deck_count_month or 0) + 1


async def enforce_compare_limit_and_increment_async(
    db: AsyncSession,
    user_id: str,
    now: datetime,
    compare_hash: str,
) -> Tuple[bool, Optional[int]]:
    """
    Re-check and increment compare usage under row lock.
    Prevents concurrent requests from over-incrementing monthly counters.
    """
    result = await db.execute(
        select(User).where(User.auth0_user_id == user_id).with_for_update()
    )
    user = result.scalar_one_or_none()
    if not user:
        return False, None

    allowed, should_increment, limit = await check_compare_limit_async(
        user,
        now,
        compare_hash,
    )
    if allowed and should_increment:
        await apply_compare_increment_async(user, now, compare_hash)

    await db.flush()
    return allowed, limit


def enforce_deck_limit_and_increment_sync(
    session: Session,
    user_id: str,
    now: datetime,
) -> Tuple[bool, Optional[int]]:
    """
    Re-check and increment deck usage under row lock.
    Prevents concurrent deck requests from bypassing monthly limits.
    """
    user = (
        session.query(User)
        .filter(User.auth0_user_id == user_id)
        .with_for_update()
        .one_or_none()
    )
    if not user:
        return False, None

    allowed, limit = check_deck_limit_sync(user, now)
    if not allowed:
        return False, limit

    increment_deck_usage_sync(user, now)
    session.flush()
    return True, limit


# =========================================================================
# LLM usage / cost helpers (for budget-aware routing & profile display)
# =========================================================================

# Thinking quota: max thinking-mode calls per day for pro users
PRO_DAILY_THINKING_LIMIT = 20


def get_daily_thinking_uses(session: Session, user_id: str) -> int:
    """Count today's thinking=True LLM calls for *user_id*."""
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    result = session.query(func.count(LLMUsageLog.id)).filter(
        LLMUsageLog.user_id == user_id,
        LLMUsageLog.thinking_enabled.is_(True),
        LLMUsageLog.created_at >= today_start,
    ).scalar()
    return result or 0


def get_monthly_model_cost(session: Session, user_id: str) -> float:
    """Sum estimated_cost_usd for the current calendar month."""
    now = datetime.utcnow()
    m_start = month_start(now)
    result = session.query(func.coalesce(func.sum(LLMUsageLog.estimated_cost_usd), 0.0)).filter(
        LLMUsageLog.user_id == user_id,
        LLMUsageLog.created_at >= m_start,
    ).scalar()
    return float(result)


async def get_daily_thinking_uses_async(db: AsyncSession, user_id: str) -> int:
    """Async variant of get_daily_thinking_uses."""
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    result = await db.execute(
        select(func.count(LLMUsageLog.id)).where(
            LLMUsageLog.user_id == user_id,
            LLMUsageLog.thinking_enabled.is_(True),
            LLMUsageLog.created_at >= today_start,
        )
    )
    return result.scalar() or 0


async def get_monthly_model_cost_async(db: AsyncSession, user_id: str) -> float:
    """Async variant of get_monthly_model_cost."""
    now = datetime.utcnow()
    m_start = month_start(now)
    result = await db.execute(
        select(func.coalesce(func.sum(LLMUsageLog.estimated_cost_usd), 0.0)).where(
            LLMUsageLog.user_id == user_id,
            LLMUsageLog.created_at >= m_start,
        )
    )
    return float(result.scalar())


def get_daily_thinking_limit(plan_tier: str) -> Optional[int]:
    """Return the daily thinking-call cap for a tier, or None if unlimited."""
    if plan_tier == "free":
        return PRO_DAILY_THINKING_LIMIT  # same cap, revisit later
    if plan_tier == "pro":
        return PRO_DAILY_THINKING_LIMIT
    return None  # enterprise = unlimited
