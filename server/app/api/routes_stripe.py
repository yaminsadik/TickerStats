"""Stripe API routes for subscription management."""
import logging
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request, Header
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.core.database import get_db
from app.models import User
from app.deck.services.stripe_service import StripeService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/stripe", tags=["stripe"])


class CreateCheckoutSessionRequest(BaseModel):
    """Request to create a Stripe checkout session."""
    tier: Literal["pro", "enterprise"]


class CreateCheckoutSessionResponse(BaseModel):
    """Response with checkout session URL."""
    url: str
    session_id: str


class CreatePortalSessionResponse(BaseModel):
    """Response with customer portal URL."""
    url: str


@router.post("/create-checkout-session", response_model=CreateCheckoutSessionResponse)
async def create_checkout_session(
    request: CreateCheckoutSessionRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Create a Stripe Checkout session for subscribing to a plan.
    
    Returns a URL to redirect the user to Stripe Checkout.
    """
    try:
        result = await StripeService.create_checkout_session(
            user=current_user,
            tier=request.tier,
            db=db,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating checkout session: {e}")
        raise HTTPException(status_code=500, detail="Failed to create checkout session")


@router.post("/create-portal-session", response_model=CreatePortalSessionResponse)
async def create_portal_session(
    current_user: User = Depends(get_current_user),
):
    """
    Create a Stripe Customer Portal session for managing subscription.
    
    Returns a URL to redirect the user to the Stripe Customer Portal.
    """
    try:
        result = await StripeService.create_portal_session(current_user)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating portal session: {e}")
        raise HTTPException(status_code=500, detail="Failed to create portal session")


@router.post("/webhook")
async def stripe_webhook(
    request: Request,
    stripe_signature: str = Header(None, alias="stripe-signature"),
    db: AsyncSession = Depends(get_db),
):
    """
    Handle Stripe webhook events.
    
    This endpoint receives events from Stripe (e.g., subscription updates).
    """
    if not stripe_signature:
        raise HTTPException(status_code=400, detail="Missing stripe-signature header")

    payload = await request.body()
    
    try:
        result = await StripeService.handle_webhook_event(
            payload=payload,
            signature=stripe_signature,
            db=db,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error processing webhook: {e}")
        raise HTTPException(status_code=500, detail="Webhook processing failed")
