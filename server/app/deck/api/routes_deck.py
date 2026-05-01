"""
FastAPI routes for deck generation.
"""

from __future__ import annotations

import asyncio
import os
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import Response
from pydantic import ValidationError

from app.core.auth import verifier
from app.core.config import settings
from app.core.database import SessionLocal
from app.core.middleware import request_id_var
from app.deck.api.schemas import (
    SECTION_METADATA,
    AnalysisDepth,
    DeckClaudeExportRequest,
    DeckGenerateRequest,
    DeckPlanRequest,
    ModelMode,
    PlanTier,
    Provider,
    ReasoningLevel,
    SectionId,
    SectionInfo,
    SectionsResponse,
)
from app.deck.services.deck_generator import DeckGenerator, DeckGeneratorConfig
from app.deck.utils.logging import get_logger
from app.deck.utils.ticker_info import enrich_request_with_ticker_info
from app.models import LLMUsageLog, User
from app.services.usage_limits import (
    check_deck_limit_sync,
    enforce_deck_limit_and_increment_sync,
    get_plan_tier,
)

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1", tags=["deck"])

_deck_generator: DeckGenerator | None = None


def _utcnow_naive() -> datetime:
    """Return current UTC time as a naive datetime (UTC semantics)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _request_id(request: Request) -> str | None:
    return request.headers.get("x-request-id") or request_id_var.get(None)


def _to_json_safe(value: Any) -> Any:
    """Recursively convert values into JSON-serializable structures."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, list):
        return [_to_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_to_json_safe(item) for item in value]
    if isinstance(value, dict):
        return {str(k): _to_json_safe(v) for k, v in value.items()}
    return str(value)


def get_deck_generator() -> DeckGenerator:
    """Get or create the deck generator instance."""
    global _deck_generator
    if _deck_generator is None:
        config = DeckGeneratorConfig(
            max_retries=int(os.getenv("DECK_MAX_RETRIES", "2")),
            timeout=int(os.getenv("DECK_TIMEOUT", "60")),
            use_cache=os.getenv("DECK_USE_CACHE", "true").lower() == "true",
            parallel_sections=os.getenv("DECK_PARALLEL_SECTIONS", "false").lower() == "true",
            max_parallel_workers=int(os.getenv("DECK_MAX_PARALLEL_WORKERS", "5")),
            section_delay_seconds=float(os.getenv("DECK_SECTION_DELAY", "0.5")),
        )
        _deck_generator = DeckGenerator(config)
    return _deck_generator


def get_api_keys(request: Request) -> dict[str, str | None]:
    """Get server-side API keys for configured LLM providers."""
    return {
        "gemini": (
            request.headers.get("X-Gemini-API-Key")
            or os.getenv("GEMINI_API_KEY")
            or os.getenv("GOOGLE_API_KEY")
        ),
        "anthropic": settings.ANTHROPIC_API_KEY or os.getenv("ANTHROPIC_API_KEY"),
    }


def _get_bearer_token(request: Request) -> str | None:
    auth_header = request.headers.get("authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header.split(" ", 1)[1].strip()
    return None


def _upsert_user_sync(session, user_id: str, payload: dict) -> User:
    """Sync upsert for deck routes using the shared User model."""
    email = (
        payload.get("email")
        or payload.get(f"https://{settings.AUTH0_DOMAIN}/email")
        or payload.get("https://tickerstats.com/email")
        or payload.get("http://tickerstats.com/email")
    )
    name = (
        payload.get("name")
        or payload.get(f"https://{settings.AUTH0_DOMAIN}/name")
        or payload.get("https://tickerstats.com/name")
        or payload.get("http://tickerstats.com/name")
        or payload.get("nickname")
    )
    picture = (
        payload.get("picture")
        or payload.get(f"https://{settings.AUTH0_DOMAIN}/picture")
        or payload.get("https://tickerstats.com/picture")
        or payload.get("http://tickerstats.com/picture")
    )

    if not email or not name:
        logger.warning(
            "Missing user info from token for %s: email=%s, name=%s. Available claims: %s",
            user_id,
            bool(email),
            bool(name),
            list(payload.keys()),
        )

    user = session.get(User, user_id)
    if user:
        changed = False
        if not user.subscription_tier:
            user.subscription_tier = "free"
            changed = True
        if email and user.email != email:
            user.email = email
            changed = True
        if name and user.name != name:
            user.name = name
            changed = True
        if picture and user.picture != picture:
            user.picture = picture
            changed = True
        if changed:
            user.updated_at = _utcnow_naive()
            session.flush()
        return user

    user = User(
        auth0_user_id=user_id,
        email=email,
        name=name,
        picture=picture,
        subscription_tier="free",
    )
    session.add(user)
    session.flush()
    return user


def _resolve_plan_and_models(
    deck_request: DeckGenerateRequest,
    api_keys: dict[str, str | None],
    plan_tier: str,
) -> tuple[str, str | None, AnalysisDepth, ModelMode]:
    """Apply plan-tier model rules and return provider, model, depth, mode."""
    from app.deck.services.model_policy import resolve_model

    model_mode = deck_request.model_mode or ModelMode.AUTO
    analysis_depth = deck_request.analysis_depth or AnalysisDepth(deck_request.reasoning_level.value)

    if plan_tier == "free" and analysis_depth == AnalysisDepth.HIGH:
        analysis_depth = AnalysisDepth.MEDIUM

    decision = resolve_model(
        plan_tier=plan_tier,
        analysis_depth=analysis_depth.value,
        model_mode=model_mode.value,
        requested_model_id=deck_request.model,
        thinking_requested=deck_request.reasoning_level == ReasoningLevel.HIGH,
        available_keys=api_keys,
    )

    return decision.provider, decision.model, analysis_depth, model_mode


def _to_int(value: Any) -> int:
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0


def _estimate_cost_usd(model: str, input_tokens: int, output_tokens: int) -> float:
    from app.deck.services.model_catalog import get_model_by_id

    model_def = get_model_by_id(model)
    if model_def is None:
        return 0.0
    return round(
        (input_tokens / 1_000_000) * model_def.input_price_per_m
        + (output_tokens / 1_000_000) * model_def.output_price_per_m,
        6,
    )


def _estimate_anthropic_export_cost_usd(model: str, input_tokens: int, output_tokens: int) -> float:
    """Best-effort Claude export cost estimate until export models join the catalog."""
    model_key = (model or "").lower()
    if "sonnet" in model_key:
        input_price_per_m = 3.0
        output_price_per_m = 15.0
    else:
        input_price_per_m = 0.0
        output_price_per_m = 0.0
    return round(
        (input_tokens / 1_000_000) * input_price_per_m
        + (output_tokens / 1_000_000) * output_price_per_m,
        6,
    )


def _infer_provider(model: str, fallback_provider: str) -> str:
    from app.deck.services.model_catalog import get_model_by_id

    model_def = get_model_by_id(model)
    return model_def.provider if model_def is not None else fallback_provider


def _record_llm_usage_sync(session, user_id: str, response, thinking_requested: bool) -> None:
    """Persist one usage-ledger row per successful section generation."""
    default_provider = response.provider_used.provider
    default_model = response.provider_used.model

    for section in response.results:
        metadata = section.generation_metadata or {}
        tokens = metadata.get("tokens") or {}
        model = str(metadata.get("model") or default_model or "")[:50]
        provider = _infer_provider(model, default_provider)[:20]
        input_tokens = _to_int(tokens.get("prompt_tokens") or tokens.get("input_tokens"))
        output_tokens = _to_int(tokens.get("completion_tokens") or tokens.get("output_tokens"))
        reasoning_tokens = _to_int(tokens.get("reasoning_tokens"))
        latency_ms = _to_int(metadata.get("latency_ms"))

        session.add(LLMUsageLog(
            user_id=user_id,
            provider=provider,
            model=model or default_model[:50],
            thinking_enabled=thinking_requested or reasoning_tokens > 0,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            reasoning_tokens=reasoning_tokens,
            estimated_cost_usd=_estimate_cost_usd(model or default_model, input_tokens, output_tokens),
            latency_ms=latency_ms,
        ))


async def _parse_model(model_cls, request: Request):
    content_type = request.headers.get("content-type", "")
    if "application/json" not in content_type.lower():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "Content-Type must be application/json",
                "request_id": _request_id(request),
            },
        )
    try:
        data = await request.json()
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "Content-Type must be application/json",
                "request_id": _request_id(request),
            },
        )
    try:
        return model_cls(**data)
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "Validation error",
                "details": _to_json_safe(exc.errors()),
                "request_id": _request_id(request),
            },
        )


@router.get("/sections")
async def get_sections():
    """Get available deck sections."""
    default_section_ids = {
        "company_snapshot",
        "overview",
        "history",
        "business_model_segments",
        "industry_competitive_landscape",
        "historical_performance_current_setup",
        "management_ownership_governance",
        "capital_structure_financial_health",
        "swot",
    }

    sections = []
    for section_id in SectionId:
        meta = SECTION_METADATA.get(section_id, {})
        sections.append(SectionInfo(
            id=section_id.value,
            label=meta.get("label", section_id.value),
            description=meta.get("description"),
            default=section_id.value in default_section_ids,
            requires_user_input=meta.get("requires_user_input", False),
        ))

    return SectionsResponse(sections=sections)


@router.post("/deck/generate")
async def generate_deck(request: Request):
    """Generate pitch deck sections."""
    deck_request = await _parse_model(DeckGenerateRequest, request)

    token = _get_bearer_token(request)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "Authentication required", "request_id": _request_id(request)},
        )

    try:
        payload = verifier.verify_token(token)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "Invalid token", "request_id": _request_id(request)},
        )

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "Invalid token: Missing subject", "request_id": _request_id(request)},
        )

    session = SessionLocal()
    try:
        user = _upsert_user_sync(session, user_id, payload)
        plan_tier = get_plan_tier(user)
        allowed, limit = check_deck_limit_sync(user, _utcnow_naive())
        session.commit()
    except Exception as exc:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "User lookup failed", "message": str(exc), "request_id": _request_id(request)},
        )
    finally:
        session.close()

    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "Deck limit reached",
                "message": f"Your plan is limited to {limit} deck generations per month.",
                "request_id": _request_id(request),
            },
        )

    try:
        company_name, sector = await asyncio.to_thread(
            enrich_request_with_ticker_info,
            ticker=deck_request.ticker,
            company_name=deck_request.company_name,
            sector=deck_request.sector,
        )
        deck_request.company_name = company_name
        deck_request.sector = sector
        logger.info("Request enriched: %s -> %s (%s)", deck_request.ticker, company_name, sector)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": str(exc), "request_id": _request_id(request)},
        )

    api_keys = get_api_keys(request)
    provider_name, model_name, analysis_depth, model_mode = _resolve_plan_and_models(
        deck_request,
        api_keys,
        plan_tier,
    )
    deck_request.plan_tier = PlanTier(plan_tier)
    deck_request.model_mode = model_mode
    deck_request.analysis_depth = analysis_depth
    deck_request.reasoning_level = ReasoningLevel(analysis_depth.value)
    deck_request.provider = Provider(provider_name)
    deck_request.model = model_name

    chosen_provider = deck_request.provider.value
    if not api_keys.get(chosen_provider):
        env_hint = {"gemini": "GEMINI_API_KEY"}.get(
            chosen_provider,
            chosen_provider.upper() + "_API_KEY",
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": f"{chosen_provider} API key required. Set {env_hint} env var.",
                "request_id": _request_id(request),
            },
        )

    generator = get_deck_generator()
    response = await asyncio.to_thread(
        generator.generate_deck,
        request=deck_request,
        api_keys=api_keys,
    )

    session = SessionLocal()
    try:
        _record_llm_usage_sync(
            session,
            user_id,
            response,
            thinking_requested=deck_request.reasoning_level == ReasoningLevel.HIGH,
        )
        allowed_after_generate, locked_limit = enforce_deck_limit_and_increment_sync(
            session,
            user_id,
            _utcnow_naive(),
        )
        if not allowed_after_generate:
            session.rollback()
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": "Deck limit reached",
                    "message": f"Your plan is limited to {locked_limit} deck generations per month.",
                    "request_id": _request_id(request),
                },
            )
        session.commit()
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning("Failed to record deck usage metadata: %s", exc)
        session.rollback()
    finally:
        session.close()

    return response


@router.post("/deck/export/claude")
async def export_deck_with_claude(request: Request):
    """Export generated deck JSON to PPTX/PDF using Claude Skills."""
    from app.deck.services.claude_export_service import (
        ClaudeDeckExportService,
        ClaudeExportError,
    )

    export_request = await _parse_model(DeckClaudeExportRequest, request)

    token = _get_bearer_token(request)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "Authentication required", "request_id": _request_id(request)},
        )

    try:
        payload = verifier.verify_token(token)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "Invalid token", "request_id": _request_id(request)},
        )

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "Invalid token: Missing subject", "request_id": _request_id(request)},
        )

    session = SessionLocal()
    try:
        user = _upsert_user_sync(session, user_id, payload)
        plan_tier = get_plan_tier(user)
        session.commit()
    except Exception as exc:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "User lookup failed", "message": str(exc), "request_id": _request_id(request)},
        )
    finally:
        session.close()

    if plan_tier == PlanTier.FREE.value and not settings.CLAUDE_EXPORT_ALLOW_FREE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "Claude export requires a Pro plan.",
                "request_id": _request_id(request),
            },
        )

    api_key = settings.ANTHROPIC_API_KEY or os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "Claude export requires ANTHROPIC_API_KEY on the server.",
                "request_id": _request_id(request),
            },
        )

    service = ClaudeDeckExportService(
        api_key=api_key,
        model=settings.CLAUDE_EXPORT_MODEL,
        cache_dir=settings.CLAUDE_EXPORT_CACHE_DIR,
        max_slides=settings.CLAUDE_EXPORT_MAX_SLIDES,
    )

    try:
        result = await asyncio.to_thread(
            service.export,
            deck=export_request.deck,
            export_format=export_request.export_format,
            title=export_request.title,
        )
    except ClaudeExportError as exc:
        message = str(exc)
        status_code = status.HTTP_400_BAD_REQUEST
        if "API error" in message or "request failed" in message or "download failed" in message:
            status_code = status.HTTP_502_BAD_GATEWAY
        raise HTTPException(
            status_code=status_code,
            detail={"error": message, "request_id": _request_id(request)},
        )

    if not result.cached:
        session = SessionLocal()
        try:
            session.add(LLMUsageLog(
                user_id=user_id,
                provider="anthropic",
                model=result.model[:50],
                thinking_enabled=False,
                input_tokens=result.input_tokens,
                output_tokens=result.output_tokens,
                reasoning_tokens=0,
                estimated_cost_usd=_estimate_anthropic_export_cost_usd(
                    result.model,
                    result.input_tokens,
                    result.output_tokens,
                ),
                latency_ms=result.latency_ms,
            ))
            session.commit()
        except Exception as exc:
            logger.warning("Failed to record Claude export usage metadata: %s", exc)
            session.rollback()
        finally:
            session.close()

    headers = {
        "Content-Disposition": f'attachment; filename="{result.filename}"',
        "X-Claude-Export-Cached": "true" if result.cached else "false",
        "X-Claude-Export-Model": result.model,
    }
    return Response(content=result.content, media_type=result.media_type, headers=headers)


@router.post("/deck/plan")
async def plan_deck(request: Request):
    """Generate a deck plan with suggested sections."""
    plan_request = await _parse_model(DeckPlanRequest, request)
    generator = get_deck_generator()
    return await asyncio.to_thread(
        generator.plan_deck,
        request=plan_request,
        api_keys=get_api_keys(request),
    )


@router.get("/deck/models")
async def get_available_models(request: Request):
    """Return the list of models available for the caller's tier."""
    from app.deck.services.model_catalog import get_catalog_for_api

    token = _get_bearer_token(request)
    tier = "free"
    if token:
        try:
            payload = verifier.verify_token(token)
            user_id = payload.get("sub")
            if user_id:
                session = SessionLocal()
                try:
                    user = _upsert_user_sync(session, user_id, payload)
                    tier = get_plan_tier(user)
                    session.commit()
                finally:
                    session.close()
        except Exception:
            pass

    return {"tier": tier, "models": get_catalog_for_api(tier)}


@router.get("/health")
async def deck_health():
    """Health check endpoint for deck service."""
    return {"status": "ok", "service": "deck-generator", "version": "1.0.0"}
