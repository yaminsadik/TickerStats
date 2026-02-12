"""Stripe integration service for subscription management."""
import logging
import os
from typing import Optional, Dict, Any
from datetime import datetime, timedelta

import stripe
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models import User

logger = logging.getLogger(__name__)

# Initialize Stripe with your secret key
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")

# Price IDs from Stripe Dashboard
PRICE_IDS = {
    "pro": os.getenv("STRIPE_PRICE_ID_PRO"),
    "enterprise": os.getenv("STRIPE_PRICE_ID_ENTERPRISE"),
}


class StripeService:
    """Service for handling Stripe operations."""

    @staticmethod
    async def create_checkout_session(
        user: User,
        tier: str,
        db: AsyncSession,
    ) -> Dict[str, str]:
        """
        Create a Stripe Checkout session for subscription purchase.
        
        Args:
            user: The user purchasing a subscription
            tier: The subscription tier ("pro" or "enterprise")
            db: Database session
            
        Returns:
            Dictionary with checkout session URL and session ID
        """
        if tier not in PRICE_IDS:
            raise ValueError(f"Invalid tier: {tier}")
        
        price_id = PRICE_IDS[tier]
        if not price_id:
            raise ValueError(f"Price ID not configured for tier: {tier}")

        # Create or retrieve Stripe customer
        if user.stripe_customer_id:
            customer_id = user.stripe_customer_id
        else:
            customer = stripe.Customer.create(
                email=user.email,
                name=user.name,
                metadata={
                    "auth0_user_id": user.auth0_user_id,
                }
            )
            customer_id = customer.id
            
            # Save customer ID to database
            user.stripe_customer_id = customer_id
            await db.commit()
            logger.info(f"Created Stripe customer {customer_id} for user {user.auth0_user_id}")

        # Create checkout session
        session = stripe.checkout.Session.create(
            customer=customer_id,
            mode="subscription",
            payment_method_types=["card"],
            line_items=[
                {
                    "price": price_id,
                    "quantity": 1,
                }
            ],
            success_url=f"{FRONTEND_URL}/profile?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{FRONTEND_URL}/profile?canceled=true",
            metadata={
                "auth0_user_id": user.auth0_user_id,
                "tier": tier,
            },
            allow_promotion_codes=True,
            billing_address_collection="auto",
        )

        logger.info(f"Created checkout session {session.id} for user {user.auth0_user_id}")
        
        return {
            "url": session.url,
            "session_id": session.id,
        }

    @staticmethod
    async def create_portal_session(user: User) -> Dict[str, str]:
        """
        Create a Stripe Customer Portal session for subscription management.
        
        Args:
            user: The user managing their subscription
            
        Returns:
            Dictionary with portal session URL
        """
        if not user.stripe_customer_id:
            raise ValueError("User does not have a Stripe customer ID")

        session = stripe.billing_portal.Session.create(
            customer=user.stripe_customer_id,
            return_url=f"{FRONTEND_URL}/profile",
        )

        return {"url": session.url}

    @staticmethod
    async def handle_webhook_event(
        payload: bytes,
        signature: str,
        db: AsyncSession,
    ) -> Dict[str, Any]:
        """
        Handle incoming Stripe webhook events.
        
        Args:
            payload: Raw request body
            signature: Stripe signature header
            db: Database session
            
        Returns:
            Dictionary with processing result
        """
        try:
            event = stripe.Webhook.construct_event(
                payload, signature, STRIPE_WEBHOOK_SECRET
            )
        except ValueError as e:
            logger.error(f"Invalid webhook payload: {e}")
            raise ValueError("Invalid payload")
        except stripe.error.SignatureVerificationError as e:
            logger.error(f"Invalid webhook signature: {e}")
            raise ValueError("Invalid signature")

        # Handle the event
        event_type = event["type"]
        data = event["data"]["object"]

        logger.info(f"Processing webhook event: {event_type}")

        if event_type == "checkout.session.completed":
            await StripeService._handle_checkout_completed(data, db)
        elif event_type == "customer.subscription.created":
            await StripeService._handle_subscription_created(data, db)
        elif event_type == "customer.subscription.updated":
            await StripeService._handle_subscription_updated(data, db)
        elif event_type == "customer.subscription.deleted":
            await StripeService._handle_subscription_deleted(data, db)
        elif event_type == "invoice.payment_succeeded":
            await StripeService._handle_payment_succeeded(data, db)
        elif event_type == "invoice.payment_failed":
            await StripeService._handle_payment_failed(data, db)
        else:
            logger.info(f"Unhandled event type: {event_type}")

        return {"status": "success", "event_type": event_type}

    @staticmethod
    async def _handle_checkout_completed(session: Dict[str, Any], db: AsyncSession):
        """Handle successful checkout session."""
        customer_id = session.get("customer")
        subscription_id = session.get("subscription")
        metadata = session.get("metadata", {})
        
        auth0_user_id = metadata.get("auth0_user_id")
        tier = metadata.get("tier")

        if not auth0_user_id:
            logger.error("No auth0_user_id in checkout session metadata")
            return

        # Get user
        result = await db.execute(
            select(User).where(User.auth0_user_id == auth0_user_id)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            logger.error(f"User not found: {auth0_user_id}")
            return

        # Update user subscription info
        user.stripe_customer_id = customer_id
        user.stripe_subscription_id = subscription_id
        
        await db.commit()
        logger.info(f"Updated user {auth0_user_id} after checkout completion")

    @staticmethod
    async def _handle_subscription_created(subscription: Dict[str, Any], db: AsyncSession):
        """Handle new subscription creation."""
        await StripeService._update_user_subscription(subscription, db)

    @staticmethod
    async def _handle_subscription_updated(subscription: Dict[str, Any], db: AsyncSession):
        """Handle subscription updates."""
        await StripeService._update_user_subscription(subscription, db)

    @staticmethod
    async def _handle_subscription_deleted(subscription: Dict[str, Any], db: AsyncSession):
        """Handle subscription cancellation."""
        customer_id = subscription.get("customer")
        
        # Find user by customer ID
        result = await db.execute(
            select(User).where(User.stripe_customer_id == customer_id)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            logger.error(f"User not found for customer {customer_id}")
            return

        # Downgrade to free tier
        user.subscription_tier = "free"
        user.stripe_subscription_id = None
        user.subscription_expires_at = None
        
        await db.commit()
        logger.info(f"Downgraded user {user.auth0_user_id} to free tier")

    @staticmethod
    async def _update_user_subscription(subscription: Dict[str, Any], db: AsyncSession):
        """Update user subscription details from Stripe subscription object."""
        customer_id = subscription.get("customer")
        subscription_id = subscription.get("id")
        status = subscription.get("status")
        
        # Find user by customer ID
        result = await db.execute(
            select(User).where(User.stripe_customer_id == customer_id)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            logger.error(f"User not found for customer {customer_id}")
            return

        # Determine tier from subscription items
        items = subscription.get("items", {}).get("data", [])
        tier = "free"
        
        if items:
            price_id = items[0].get("price", {}).get("id")
            # Map price ID to tier
            for t, pid in PRICE_IDS.items():
                if pid == price_id:
                    tier = t
                    break

        # Update user based on subscription status
        if status in ["active", "trialing"]:
            user.subscription_tier = tier
            user.stripe_subscription_id = subscription_id
            
            # Set expiration date from current period end
            current_period_end = subscription.get("current_period_end")
            if current_period_end:
                user.subscription_expires_at = datetime.utcfromtimestamp(current_period_end)
        elif status in ["canceled", "unpaid", "past_due"]:
            # Keep access until period ends
            current_period_end = subscription.get("current_period_end")
            if current_period_end:
                user.subscription_expires_at = datetime.utcfromtimestamp(current_period_end)
        
        await db.commit()
        logger.info(f"Updated subscription for user {user.auth0_user_id}: tier={tier}, status={status}")

    @staticmethod
    async def _handle_payment_succeeded(invoice: Dict[str, Any], db: AsyncSession):
        """Handle successful payment."""
        customer_id = invoice.get("customer")
        subscription_id = invoice.get("subscription")
        
        logger.info(f"Payment succeeded for customer {customer_id}, subscription {subscription_id}")
        # Subscription update webhook will handle the actual update

    @staticmethod
    async def _handle_payment_failed(invoice: Dict[str, Any], db: AsyncSession):
        """Handle failed payment."""
        customer_id = invoice.get("customer")
        subscription_id = invoice.get("subscription")
        
        logger.warning(f"Payment failed for customer {customer_id}, subscription {subscription_id}")
        # Stripe will handle retries automatically