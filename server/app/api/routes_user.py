"""User-related API routes (profile, watchlists, saved analyses, decks, admin)."""
import logging
from datetime import datetime, timezone
from typing import List, Optional, Literal
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, func, update
from pydantic import BaseModel, Field

from app.core.auth import (
    get_current_user_with_upsert,
    require_admin,
    require_paid_or_admin,
)
from app.core.database import get_db
from app.core.middleware import request_id_var
from app.models import User, Watchlist, SavedAnalysis, Deck, AdminAuditLog
from app.services.usage_limits import (
    get_plan_tier,
    get_compare_limit,
    get_deck_limit,
    reset_monthly_usage,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Free-tier limits
# ---------------------------------------------------------------------------
FREE_TIER_MAX_SAVED_SEARCHES = 3


router = APIRouter(prefix="/api/user", tags=["user"])


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

# --- Watchlist ---
class WatchlistCreate(BaseModel):
    ticker: str
    notes: Optional[str] = None


class WatchlistUpdateNotes(BaseModel):
    notes: Optional[str] = None


class WatchlistResponse(BaseModel):
    id: int
    ticker: str
    notes: Optional[str]
    created_at: str

    class Config:
        from_attributes = True


# --- Saved Analysis ---
class SavedAnalysisCreate(BaseModel):
    name: str
    description: Optional[str] = None
    symbols: List[str]
    snapshot_fields: Optional[List[str]] = None
    perf_periods: Optional[List[str]] = None
    include_dcf: bool = False
    snapshot_data: Optional[dict] = None


class SavedAnalysisResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    symbols: List[str]
    snapshot_fields: Optional[List[str]]
    perf_periods: Optional[List[str]]
    include_dcf: bool
    snapshot_data: Optional[dict]
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


# --- Deck ---
class DeckCreate(BaseModel):
    ticker: str
    title: str
    content: dict
    llm_provider: Optional[str] = None


class DeckMetaResponse(BaseModel):
    """Metadata-only response for list endpoint (no content)."""
    id: int
    ticker: str
    title: str
    llm_provider: Optional[str]
    created_at: str

    class Config:
        from_attributes = True


class DeckFullResponse(BaseModel):
    """Full response including content JSON."""
    id: int
    ticker: str
    title: str
    content: dict
    llm_provider: Optional[str]
    created_at: str

    class Config:
        from_attributes = True


# --- Profile ---
class ProfileResponse(BaseModel):
    auth0_user_id: str
    email: Optional[str]
    name: Optional[str]
    picture: Optional[str]
    subscription_tier: str
    plan_tier: str
    subscription_expires_at: Optional[str]
    is_admin: bool
    created_at: str
    updated_at: str
    saved_searches_count: int = 0
    saved_searches_limit: int = FREE_TIER_MAX_SAVED_SEARCHES
    compare_count_month: int = 0
    compare_limit: Optional[int] = None
    deck_count_month: int = 0
    deck_limit: Optional[int] = None
    can_export: bool = False

    class Config:
        from_attributes = True


class ProfileUpdate(BaseModel):
    name: Optional[str] = None
    picture: Optional[str] = None


# --- Admin ---
class AdminUserResponse(BaseModel):
    auth0_user_id: str
    email: Optional[str]
    name: Optional[str]
    picture: Optional[str]
    subscription_tier: Literal["free", "pro", "enterprise"]
    stripe_customer_id: Optional[str]
    subscription_expires_at: Optional[str]
    is_admin: bool
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


class AdminUserUpdate(BaseModel):
    subscription_tier: Optional[Literal["free", "pro", "enterprise"]] = None
    is_admin: Optional[bool] = None
    subscription_expires_at: Optional[datetime] = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _watchlist_to_response(item: Watchlist) -> WatchlistResponse:
    return WatchlistResponse(
        id=item.id,
        ticker=item.ticker,
        notes=item.notes,
        created_at=item.created_at.isoformat(),
    )


def _analysis_to_response(a: SavedAnalysis) -> SavedAnalysisResponse:
    return SavedAnalysisResponse(
        id=a.id,
        name=a.name,
        description=a.description,
        symbols=a.symbols,
        snapshot_fields=a.snapshot_fields,
        perf_periods=a.perf_periods,
        include_dcf=a.include_dcf,
        snapshot_data=a.snapshot_data,
        created_at=a.created_at.isoformat(),
        updated_at=a.updated_at.isoformat(),
    )


def _deck_meta(d: Deck) -> DeckMetaResponse:
    return DeckMetaResponse(
        id=d.id,
        ticker=d.ticker,
        title=d.title,
        llm_provider=d.llm_provider,
        created_at=d.created_at.isoformat(),
    )


def _deck_full(d: Deck) -> DeckFullResponse:
    return DeckFullResponse(
        id=d.id,
        ticker=d.ticker,
        title=d.title,
        content=d.content,
        llm_provider=d.llm_provider,
        created_at=d.created_at.isoformat(),
    )


def _set_link_headers(
    response: Response,
    request: Request,
    offset: int,
    limit: int,
    total: int,
) -> None:
    """Build RFC 5988 Link headers using the actual request URL."""
    links = []
    if offset + limit < total:
        next_url = str(request.url.include_query_params(
            offset=offset + limit, limit=limit
        ))
        links.append(f'<{next_url}>; rel="next"')
    if offset > 0:
        prev_offset = max(0, offset - limit)
        prev_url = str(request.url.include_query_params(
            offset=prev_offset, limit=limit
        ))
        links.append(f'<{prev_url}>; rel="prev"')
    if links:
        response.headers["Link"] = ", ".join(links)


# ---------------------------------------------------------------------------
# WATCHLIST ROUTES
# ---------------------------------------------------------------------------

@router.get("/watchlist", response_model=List[WatchlistResponse])
async def get_watchlist(
    request: Request,
    response: Response,
    limit: Optional[int] = Query(None, ge=1, le=500, description="Max items to return. Omit for all."),
    offset: int = Query(0, ge=0, description="Number of items to skip."),
    current_user: User = Depends(get_current_user_with_upsert),
    db: AsyncSession = Depends(get_db),
):
    """Get user's watchlist, ordered by created_at DESC. Supports optional pagination."""
    # Total count (always emitted)
    total = (await db.execute(
        select(func.count()).where(Watchlist.user_id == current_user.auth0_user_id)
    )).scalar() or 0

    # Build query
    query = (
        select(Watchlist)
        .where(Watchlist.user_id == current_user.auth0_user_id)
        .order_by(Watchlist.created_at.desc())
    )
    if limit is not None:
        query = query.limit(limit).offset(offset)

    result = await db.execute(query)
    items = [_watchlist_to_response(item) for item in result.scalars().all()]

    # Headers
    response.headers["X-Total-Count"] = str(total)
    if limit is not None:
        _set_link_headers(response, request, offset, limit, total)

    return items


@router.post("/watchlist", response_model=WatchlistResponse, status_code=status.HTTP_201_CREATED)
async def add_to_watchlist(
    item: WatchlistCreate,
    current_user: User = Depends(get_current_user_with_upsert),
    db: AsyncSession = Depends(get_db),
):
    """Add ticker to watchlist. Ticker is uppercased. Duplicates return 409."""
    ticker = item.ticker.strip().upper()
    # Check for existing
    result = await db.execute(
        select(Watchlist).where(
            Watchlist.user_id == current_user.auth0_user_id,
            Watchlist.ticker == ticker,
        )
    )
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Ticker {ticker} already in watchlist",
        )

    watchlist_item = Watchlist(
        user_id=current_user.auth0_user_id,
        ticker=ticker,
        notes=item.notes,
    )
    db.add(watchlist_item)
    await db.flush()
    await db.refresh(watchlist_item)
    return _watchlist_to_response(watchlist_item)


@router.patch("/watchlist/{item_id}", response_model=WatchlistResponse)
async def update_watchlist_notes(
    item_id: int,
    body: WatchlistUpdateNotes,
    current_user: User = Depends(get_current_user_with_upsert),
    db: AsyncSession = Depends(get_db),
):
    """Update notes on a watchlist entry."""
    result = await db.execute(
        select(Watchlist).where(
            Watchlist.id == item_id,
            Watchlist.user_id == current_user.auth0_user_id,
        )
    )
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Watchlist entry not found")

    item.notes = body.notes
    await db.flush()
    await db.refresh(item)
    return _watchlist_to_response(item)


@router.delete("/watchlist/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_from_watchlist(
    item_id: int,
    current_user: User = Depends(get_current_user_with_upsert),
    db: AsyncSession = Depends(get_db),
):
    """Remove an entry from watchlist by id."""
    result = await db.execute(
        delete(Watchlist).where(
            Watchlist.id == item_id,
            Watchlist.user_id == current_user.auth0_user_id,
        )
    )
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Watchlist entry not found")


# ---------------------------------------------------------------------------
# SAVED ANALYSES ROUTES
# ---------------------------------------------------------------------------

@router.get("/saved-analyses", response_model=List[SavedAnalysisResponse])
async def list_saved_analyses(
    request: Request,
    response: Response,
    limit: Optional[int] = Query(None, ge=1, le=500, description="Max items to return. Omit for all."),
    offset: int = Query(0, ge=0, description="Number of items to skip."),
    current_user: User = Depends(get_current_user_with_upsert),
    db: AsyncSession = Depends(get_db),
):
    """List user's saved analyses, ordered by created_at DESC. Supports optional pagination."""
    total = (await db.execute(
        select(func.count()).where(SavedAnalysis.user_id == current_user.auth0_user_id)
    )).scalar() or 0

    query = (
        select(SavedAnalysis)
        .where(SavedAnalysis.user_id == current_user.auth0_user_id)
        .order_by(SavedAnalysis.created_at.desc())
    )
    if limit is not None:
        query = query.limit(limit).offset(offset)

    result = await db.execute(query)
    items = [_analysis_to_response(a) for a in result.scalars().all()]

    response.headers["X-Total-Count"] = str(total)
    if limit is not None:
        _set_link_headers(response, request, offset, limit, total)

    return items


@router.post("/saved-analyses", response_model=SavedAnalysisResponse, status_code=status.HTTP_201_CREATED)
async def create_saved_analysis(
    body: SavedAnalysisCreate,
    current_user: User = Depends(get_current_user_with_upsert),
    db: AsyncSession = Depends(get_db),
):
    """Save a new analysis configuration. Free tier limited to 3."""
    # Enforce free-tier limit
    if not current_user.is_paid and not current_user.is_admin:
        count_result = await db.execute(
            select(func.count()).where(
                SavedAnalysis.user_id == current_user.auth0_user_id
            )
        )
        count = count_result.scalar() or 0
        if count >= FREE_TIER_MAX_SAVED_SEARCHES:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Free tier is limited to {FREE_TIER_MAX_SAVED_SEARCHES} saved searches. Upgrade to Pro for unlimited.",
            )

    analysis = SavedAnalysis(
        user_id=current_user.auth0_user_id,
        name=body.name,
        description=body.description,
        symbols=[s.upper() for s in body.symbols],
        snapshot_fields=body.snapshot_fields,
        perf_periods=body.perf_periods,
        include_dcf=body.include_dcf,
        snapshot_data=body.snapshot_data,
    )
    db.add(analysis)
    await db.flush()
    await db.refresh(analysis)
    return _analysis_to_response(analysis)


@router.get("/saved-analyses/{analysis_id}", response_model=SavedAnalysisResponse)
async def get_saved_analysis(
    analysis_id: int,
    current_user: User = Depends(get_current_user_with_upsert),
    db: AsyncSession = Depends(get_db),
):
    """Get a single saved analysis by ID."""
    result = await db.execute(
        select(SavedAnalysis).where(
            SavedAnalysis.id == analysis_id,
            SavedAnalysis.user_id == current_user.auth0_user_id,
        )
    )
    analysis = result.scalar_one_or_none()
    if not analysis:
        raise HTTPException(status_code=404, detail="Saved analysis not found")
    return _analysis_to_response(analysis)


@router.delete("/saved-analyses/{analysis_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_saved_analysis(
    analysis_id: int,
    current_user: User = Depends(get_current_user_with_upsert),
    db: AsyncSession = Depends(get_db),
):
    """Delete a saved analysis."""
    result = await db.execute(
        delete(SavedAnalysis).where(
            SavedAnalysis.id == analysis_id,
            SavedAnalysis.user_id == current_user.auth0_user_id,
        )
    )
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Saved analysis not found")


# ---------------------------------------------------------------------------
# DECK ROUTES
# ---------------------------------------------------------------------------

@router.get("/decks", response_model=List[DeckMetaResponse])
async def list_decks(
    request: Request,
    response: Response,
    limit: Optional[int] = Query(None, ge=1, le=500, description="Max items to return. Omit for all."),
    offset: int = Query(0, ge=0, description="Number of items to skip."),
    current_user: User = Depends(get_current_user_with_upsert),
    db: AsyncSession = Depends(get_db),
):
    """List user's generated decks (metadata only), ordered by created_at DESC. Supports optional pagination."""
    total = (await db.execute(
        select(func.count()).where(Deck.user_id == current_user.auth0_user_id)
    )).scalar() or 0

    query = (
        select(Deck)
        .where(Deck.user_id == current_user.auth0_user_id)
        .order_by(Deck.created_at.desc())
    )
    if limit is not None:
        query = query.limit(limit).offset(offset)

    result = await db.execute(query)
    items = [_deck_meta(d) for d in result.scalars().all()]

    response.headers["X-Total-Count"] = str(total)
    if limit is not None:
        _set_link_headers(response, request, offset, limit, total)

    return items


@router.post("/decks", response_model=DeckFullResponse, status_code=status.HTTP_201_CREATED)
async def create_deck(
    body: DeckCreate,
    current_user: User = Depends(get_current_user_with_upsert),
    db: AsyncSession = Depends(get_db),
):
    """Save a generated deck to the database."""
    deck = Deck(
        user_id=current_user.auth0_user_id,
        ticker=body.ticker.strip().upper(),
        title=body.title,
        content=body.content,
        llm_provider=body.llm_provider,
    )
    db.add(deck)
    await db.flush()
    await db.refresh(deck)
    return _deck_full(deck)


@router.get("/decks/{deck_id}", response_model=DeckFullResponse)
async def get_deck(
    deck_id: int,
    current_user: User = Depends(get_current_user_with_upsert),
    db: AsyncSession = Depends(get_db),
):
    """Get a specific deck by ID (includes full content)."""
    result = await db.execute(
        select(Deck).where(
            Deck.id == deck_id,
            Deck.user_id == current_user.auth0_user_id,
        )
    )
    deck = result.scalar_one_or_none()
    if not deck:
        raise HTTPException(status_code=404, detail="Deck not found")
    return _deck_full(deck)


@router.delete("/decks/{deck_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_deck(
    deck_id: int,
    current_user: User = Depends(get_current_user_with_upsert),
    db: AsyncSession = Depends(get_db),
):
    """Delete a deck."""
    result = await db.execute(
        delete(Deck).where(
            Deck.id == deck_id,
            Deck.user_id == current_user.auth0_user_id,
        )
    )
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Deck not found")


# ---------------------------------------------------------------------------
# PROFILE ROUTES
# ---------------------------------------------------------------------------

@router.get("/profile", response_model=ProfileResponse)
async def get_profile(
    current_user: User = Depends(get_current_user_with_upsert),
    db: AsyncSession = Depends(get_db),
):
    """Get the current user's profile, including subscription status and usage."""
    now = datetime.utcnow()
    if reset_monthly_usage(current_user, now):
        current_user.updated_at = now
        await db.flush()
    count_result = await db.execute(
        select(func.count()).where(
            SavedAnalysis.user_id == current_user.auth0_user_id
        )
    )
    saved_count = count_result.scalar() or 0

    is_paid = current_user.is_paid
    plan_tier = get_plan_tier(current_user)
    compare_limit = get_compare_limit(plan_tier)
    deck_limit = get_deck_limit(plan_tier)
    return ProfileResponse(
        auth0_user_id=current_user.auth0_user_id,
        email=current_user.email,
        name=current_user.name,
        picture=current_user.picture,
        subscription_tier=current_user.subscription_tier,
        plan_tier=plan_tier,
        subscription_expires_at=(
            current_user.subscription_expires_at.isoformat()
            if current_user.subscription_expires_at
            else None
        ),
        is_admin=current_user.is_admin,
        created_at=current_user.created_at.isoformat(),
        updated_at=current_user.updated_at.isoformat(),
        saved_searches_count=saved_count,
        saved_searches_limit=999 if is_paid else FREE_TIER_MAX_SAVED_SEARCHES,
        compare_count_month=current_user.compare_count_month or 0,
        compare_limit=compare_limit,
        deck_count_month=current_user.deck_count_month or 0,
        deck_limit=deck_limit,
        can_export=is_paid or current_user.is_admin,
    )


@router.patch("/profile", response_model=ProfileResponse)
async def update_profile(
    body: ProfileUpdate,
    current_user: User = Depends(get_current_user_with_upsert),
    db: AsyncSession = Depends(get_db),
):
    """Update mutable profile fields (name, picture)."""
    changed = False
    if body.name is not None and body.name != current_user.name:
        current_user.name = body.name
        changed = True
    if body.picture is not None and body.picture != current_user.picture:
        current_user.picture = body.picture
        changed = True
    if changed:
        current_user.updated_at = datetime.utcnow()
        await db.flush()
        await db.refresh(current_user)

    now = datetime.utcnow()
    if reset_monthly_usage(current_user, now):
        current_user.updated_at = now
        await db.flush()

    # Re-fetch counts for response
    count_result = await db.execute(
        select(func.count()).where(
            SavedAnalysis.user_id == current_user.auth0_user_id
        )
    )
    saved_count = count_result.scalar() or 0
    is_paid = current_user.is_paid
    plan_tier = get_plan_tier(current_user)
    compare_limit = get_compare_limit(plan_tier)
    deck_limit = get_deck_limit(plan_tier)

    return ProfileResponse(
        auth0_user_id=current_user.auth0_user_id,
        email=current_user.email,
        name=current_user.name,
        picture=current_user.picture,
        subscription_tier=current_user.subscription_tier,
        plan_tier=plan_tier,
        subscription_expires_at=(
            current_user.subscription_expires_at.isoformat()
            if current_user.subscription_expires_at
            else None
        ),
        is_admin=current_user.is_admin,
        created_at=current_user.created_at.isoformat(),
        updated_at=current_user.updated_at.isoformat(),
        saved_searches_count=saved_count,
        saved_searches_limit=999 if is_paid else FREE_TIER_MAX_SAVED_SEARCHES,
        compare_count_month=current_user.compare_count_month or 0,
        compare_limit=compare_limit,
        deck_count_month=current_user.deck_count_month or 0,
        deck_limit=deck_limit,
        can_export=is_paid or current_user.is_admin,
    )


# ---------------------------------------------------------------------------
# ADMIN ROUTES
# ---------------------------------------------------------------------------

admin_router = APIRouter(prefix="/api/admin", tags=["admin"])


@admin_router.get("/users", response_model=List[AdminUserResponse])
async def admin_list_users(
    request: Request,
    response: Response,
    limit: Optional[int] = Query(None, ge=1, le=500, description="Max items to return. Omit for all."),
    offset: int = Query(0, ge=0, description="Number of items to skip."),
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """List all users (admin only). Supports optional pagination."""
    total = (await db.execute(
        select(func.count()).select_from(User)
    )).scalar() or 0

    query = select(User).order_by(User.created_at.desc())
    if limit is not None:
        query = query.limit(limit).offset(offset)

    result = await db.execute(query)
    users = result.scalars().all()

    response.headers["X-Total-Count"] = str(total)
    if limit is not None:
        _set_link_headers(response, request, offset, limit, total)

    return [
        AdminUserResponse(
            auth0_user_id=u.auth0_user_id,
            email=u.email,
            name=u.name,
            picture=u.picture,
            subscription_tier=u.subscription_tier,
            stripe_customer_id=u.stripe_customer_id,
            subscription_expires_at=(
                u.subscription_expires_at.isoformat()
                if u.subscription_expires_at
                else None
            ),
            is_admin=u.is_admin,
            created_at=u.created_at.isoformat(),
            updated_at=u.updated_at.isoformat(),
        )
        for u in users
    ]


@admin_router.patch("/users/{user_id}", response_model=AdminUserResponse)
async def admin_update_user(
    user_id: str,
    body: AdminUserUpdate,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Update a user's subscription tier, admin status, or expiry (admin only).
    All changes are recorded in the admin_audit_log table."""
    result = await db.execute(
        select(User).where(User.auth0_user_id == user_id)
    )
    target = result.scalar_one_or_none()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    req_id = request_id_var.get(None)

    # --- Tier change ---
    if body.subscription_tier is not None:
        if body.subscription_tier != target.subscription_tier:
            db.add(AdminAuditLog(
                admin_user_id=admin.auth0_user_id,
                target_user_id=user_id,
                action="update_tier",
                old_value=target.subscription_tier,
                new_value=body.subscription_tier,
                request_id=req_id,
            ))
            logger.info(
                "Admin tier change: %s -> %s for user %s by %s",
                target.subscription_tier, body.subscription_tier,
                user_id, admin.auth0_user_id,
                extra={"request_id": req_id},
            )
            target.subscription_tier = body.subscription_tier

    # --- Admin toggle ---
    if body.is_admin is not None and body.is_admin != target.is_admin:
        if not body.is_admin and target.auth0_user_id == admin.auth0_user_id:
            raise HTTPException(
                status_code=400,
                detail="You cannot remove your own admin access.",
            )

        if not body.is_admin and target.is_admin:
            admin_count = (await db.execute(
                select(func.count()).select_from(User).where(User.is_admin.is_(True))
            )).scalar() or 0
            if admin_count <= 1:
                raise HTTPException(
                    status_code=400,
                    detail="Cannot remove admin access from the last admin.",
                )

        db.add(AdminAuditLog(
            admin_user_id=admin.auth0_user_id,
            target_user_id=user_id,
            action="toggle_admin",
            old_value=target.is_admin,
            new_value=body.is_admin,
            request_id=req_id,
        ))
        logger.info(
            "Admin toggle: %s -> %s for user %s by %s",
            target.is_admin, body.is_admin,
            user_id, admin.auth0_user_id,
            extra={"request_id": req_id},
        )
        target.is_admin = body.is_admin

    # --- Expiry change ---
    if body.subscription_expires_at is not None:
        new_expiry_dt = body.subscription_expires_at
        if new_expiry_dt.tzinfo is not None:
            new_expiry_dt = new_expiry_dt.astimezone(timezone.utc).replace(tzinfo=None)

        old_expiry = target.subscription_expires_at.isoformat() if target.subscription_expires_at else None
        new_expiry_iso = new_expiry_dt.isoformat()
        db.add(AdminAuditLog(
            admin_user_id=admin.auth0_user_id,
            target_user_id=user_id,
            action="update_expiry",
            old_value=old_expiry,
            new_value=new_expiry_iso,
            request_id=req_id,
        ))
        logger.info(
            "Admin expiry change: %s -> %s for user %s by %s",
            old_expiry, new_expiry_iso,
            user_id, admin.auth0_user_id,
            extra={"request_id": req_id},
        )
        target.subscription_expires_at = new_expiry_dt

    target.updated_at = datetime.utcnow()
    await db.flush()
    await db.refresh(target)

    return AdminUserResponse(
        auth0_user_id=target.auth0_user_id,
        email=target.email,
        name=target.name,
        picture=target.picture,
        subscription_tier=target.subscription_tier,
        stripe_customer_id=target.stripe_customer_id,
        subscription_expires_at=(
            target.subscription_expires_at.isoformat()
            if target.subscription_expires_at
            else None
        ),
        is_admin=target.is_admin,
        created_at=target.created_at.isoformat(),
        updated_at=target.updated_at.isoformat(),
    )


@admin_router.get("/stats")
async def admin_stats(
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Dashboard stats for admin panel."""
    total_users = (await db.execute(select(func.count()).select_from(User))).scalar() or 0
    paid_users = (await db.execute(
        select(func.count()).select_from(User).where(User.subscription_tier != "free")
    )).scalar() or 0
    total_analyses = (await db.execute(select(func.count()).select_from(SavedAnalysis))).scalar() or 0
    total_decks = (await db.execute(select(func.count()).select_from(Deck))).scalar() or 0
    total_watchlist = (await db.execute(select(func.count()).select_from(Watchlist))).scalar() or 0

    return {
        "total_users": total_users,
        "paid_users": paid_users,
        "free_users": total_users - paid_users,
        "total_saved_analyses": total_analyses,
        "total_decks": total_decks,
        "total_watchlist_items": total_watchlist,
    }
