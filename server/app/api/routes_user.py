"""User-related API routes (profile, watchlists, saved analyses)."""
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from pydantic import BaseModel

from app.core.auth import get_current_user
from app.core.database import get_db
from app.models import User, Watchlist, SavedAnalysis, Deck


router = APIRouter(prefix="/api/user", tags=["user"])


# Pydantic schemas
class WatchlistItem(BaseModel):
    ticker: str
    notes: str | None = None


class WatchlistResponse(BaseModel):
    id: int
    ticker: str
    notes: str | None
    created_at: str
    
    class Config:
        from_attributes = True


class SavedAnalysisCreate(BaseModel):
    name: str
    description: str | None = None
    symbols: List[str]
    snapshot_fields: List[str] | None = None
    perf_periods: List[str] | None = None
    include_dcf: bool = False


class SavedAnalysisResponse(BaseModel):
    id: int
    name: str
    description: str | None
    symbols: List[str]
    snapshot_fields: List[str] | None
    perf_periods: List[str] | None
    include_dcf: bool
    created_at: str
    updated_at: str
    
    class Config:
        from_attributes = True


class DeckResponse(BaseModel):
    id: int
    ticker: str
    title: str
    content: dict
    llm_provider: str | None
    created_at: str
    
    class Config:
        from_attributes = True


# ===== WATCHLIST ROUTES =====

@router.get("/watchlist", response_model=List[WatchlistResponse])
async def get_watchlist(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get user's watchlist."""
    result = await db.execute(
        select(Watchlist)
        .where(Watchlist.user_id == current_user.auth0_user_id)
        .order_by(Watchlist.created_at.desc())
    )
    items = result.scalars().all()
    return [
        WatchlistResponse(
            id=item.id,
            ticker=item.ticker,
            notes=item.notes,
            created_at=item.created_at.isoformat(),
        )
        for item in items
    ]


@router.post("/watchlist", response_model=WatchlistResponse, status_code=status.HTTP_201_CREATED)
async def add_to_watchlist(
    item: WatchlistItem,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Add ticker to watchlist."""
    # Check if already exists
    result = await db.execute(
        select(Watchlist).where(
            Watchlist.user_id == current_user.auth0_user_id,
            Watchlist.ticker == item.ticker.upper(),
        )
    )
    existing = result.scalar_one_or_none()
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Ticker {item.ticker} already in watchlist",
        )
    
    watchlist_item = Watchlist(
        user_id=current_user.auth0_user_id,
        ticker=item.ticker.upper(),
        notes=item.notes,
    )
    db.add(watchlist_item)
    await db.commit()
    await db.refresh(watchlist_item)
    
    return WatchlistResponse(
        id=watchlist_item.id,
        ticker=watchlist_item.ticker,
        notes=watchlist_item.notes,
        created_at=watchlist_item.created_at.isoformat(),
    )


@router.delete("/watchlist/{ticker}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_from_watchlist(
    ticker: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Remove ticker from watchlist."""
    result = await db.execute(
        delete(Watchlist).where(
            Watchlist.user_id == current_user.auth0_user_id,
            Watchlist.ticker == ticker.upper(),
        )
    )
    
    if result.rowcount == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Ticker {ticker} not found in watchlist",
        )
    
    await db.commit()


# ===== SAVED ANALYSES ROUTES =====

@router.get("/analyses", response_model=List[SavedAnalysisResponse])
async def get_saved_analyses(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get user's saved analyses."""
    result = await db.execute(
        select(SavedAnalysis)
        .where(SavedAnalysis.user_id == current_user.auth0_user_id)
        .order_by(SavedAnalysis.updated_at.desc())
    )
    analyses = result.scalars().all()
    return [
        SavedAnalysisResponse(
            id=analysis.id,
            name=analysis.name,
            description=analysis.description,
            symbols=analysis.symbols,
            snapshot_fields=analysis.snapshot_fields,
            perf_periods=analysis.perf_periods,
            include_dcf=analysis.include_dcf,
            created_at=analysis.created_at.isoformat(),
            updated_at=analysis.updated_at.isoformat(),
        )
        for analysis in analyses
    ]


@router.post("/analyses", response_model=SavedAnalysisResponse, status_code=status.HTTP_201_CREATED)
async def create_saved_analysis(
    analysis: SavedAnalysisCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Save a new analysis configuration."""
    saved_analysis = SavedAnalysis(
        user_id=current_user.auth0_user_id,
        name=analysis.name,
        description=analysis.description,
        symbols=analysis.symbols,
        snapshot_fields=analysis.snapshot_fields,
        perf_periods=analysis.perf_periods,
        include_dcf=analysis.include_dcf,
    )
    db.add(saved_analysis)
    await db.commit()
    await db.refresh(saved_analysis)
    
    return SavedAnalysisResponse(
        id=saved_analysis.id,
        name=saved_analysis.name,
        description=saved_analysis.description,
        symbols=saved_analysis.symbols,
        snapshot_fields=saved_analysis.snapshot_fields,
        perf_periods=saved_analysis.perf_periods,
        include_dcf=saved_analysis.include_dcf,
        created_at=saved_analysis.created_at.isoformat(),
        updated_at=saved_analysis.updated_at.isoformat(),
    )


@router.delete("/analyses/{analysis_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_saved_analysis(
    analysis_id: int,
    current_user: User = Depends(get_current_user),
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
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Analysis not found",
        )
    
    await db.commit()


# ===== DECK HISTORY ROUTES =====

@router.get("/decks", response_model=List[DeckResponse])
async def get_saved_decks(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get user's generated decks."""
    result = await db.execute(
        select(Deck)
        .where(Deck.user_id == current_user.auth0_user_id)
        .order_by(Deck.created_at.desc())
        .limit(50)  # Limit to recent 50
    )
    decks = result.scalars().all()
    return [
        DeckResponse(
            id=deck.id,
            ticker=deck.ticker,
            title=deck.title,
            content=deck.content,
            llm_provider=deck.llm_provider,
            created_at=deck.created_at.isoformat(),
        )
        for deck in decks
    ]


@router.get("/decks/{deck_id}", response_model=DeckResponse)
async def get_deck_by_id(
    deck_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a specific deck by ID."""
    result = await db.execute(
        select(Deck).where(
            Deck.id == deck_id,
            Deck.user_id == current_user.auth0_user_id,
        )
    )
    deck = result.scalar_one_or_none()
    
    if not deck:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Deck not found",
        )
    
    return DeckResponse(
        id=deck.id,
        ticker=deck.ticker,
        title=deck.title,
        content=deck.content,
        llm_provider=deck.llm_provider,
        created_at=deck.created_at.isoformat(),
    )
