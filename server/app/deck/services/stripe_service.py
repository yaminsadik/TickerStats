"""Stripe integration service for subscription management."""
import logging
from datetime import datetime
from typing import Any, Dict

import stripe
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models import User

logger = logging.getLogger(__name__)

# Initialize Stripe with your secret key
stripe.api_key = settings.STRIPE_SECRET_KEY or None
STRIPE_WEBHOOK_SECRET = settings.STRIPE_WEBHOOK_SECRET
FRONTEND_URL = settings.FRONTEND_URL


def _price_ids() -> Dict[str, str]:
    """Return configured Stripe Price IDs by tier."""
    return {
        "pro": settings.STRIPE_PRICE_ID_PRO,
        "enterprise": settings.STRIPE_PRICE_ID_ENTERPRISE,
    }


class StripeService:
    """Service for handling Stripe operations."""

    @staticmethod
    def _create_checkout_session_payload(
        customer_id: str,
        price_id: str,
        user: User,
        tier: str,
    ):
        """Create a Stripe checkout session request payload."""
        return stripe.checkout.Session.create(
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

    @staticmethod
    def _is_missing_customer_error(exc: stripe.error.InvalidRequestError) -> bool:
        """Return True when Stripe says the referenced customer no longer exists."""
        message = str(exc).lower()
        return "no such customer" in message or getattr(exc, "code", None) == "resource_missing"

    @staticmethod
    async def _ensure_stripe_customer_id(user: User, db: AsyncSession) -> str:
        """
        Return a valid Stripe customer ID for the user.
        If a stored customer ID is stale/deleted, transparently create a replacement.
        """
        if user.stripe_customer_id:
            try:
                customer = stripe.Customer.retrieve(user.stripe_customer_id)
                if not getattr(customer, "deleted", False):
                    return user.stripe_customer_id
            except stripe.error.InvalidRequestError as exc:
                if not StripeService._is_missing_customer_error(exc):
                    raise
                logger.warning(
                    f"Stale Stripe customer ID for user {user.auth0_user_id}: "
                    f"{user.stripe_customer_id}. Creating a new customer."
                )

        customer = stripe.Customer.create(
            email=user.email,
            name=user.name,
            metadata={
                "auth0_user_id": user.auth0_user_id,
            },
        )
        user.stripe_customer_id = customer.id
        await db.commit()
        logger.info(f"Created Stripe customer {customer.id} for user {user.auth0_user_id}")
        return customer.id

    @staticmethod
    async def _find_user_by_customer_id(
        customer_id: str | None,
        db: AsyncSession,
    ) -> User | None:
        """Find user by Stripe customer ID."""
        if not customer_id:
            return None

        result = await db.execute(
            select(User).where(User.stripe_customer_id == customer_id)
        )
        return result.scalar_one_or_none()

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
        if not settings.STRIPE_SECRET_KEY:
            raise ValueError("Stripe secret key is not configured")

        price_ids = _price_ids()
        if tier not in price_ids:
            raise ValueError(f"Invalid tier: {tier}")

        price_id = price_ids[tier]
        if not price_id:
            raise ValueError(f"Price ID not configured for tier: {tier}")

        try:
            customer_id = await StripeService._ensure_stripe_customer_id(user, db)
            try:
                session = StripeService._create_checkout_session_payload(
                    customer_id=customer_id,
                    price_id=price_id,
                    user=user,
                    tier=tier,
                )
            except stripe.error.InvalidRequestError as exc:
                # Recover if customer was deleted between retrieve and checkout session create.
                if not StripeService._is_missing_customer_error(exc):
                    raise
                logger.warning(
                    f"Stripe customer disappeared during checkout for user {user.auth0_user_id}: "
                    f"{customer_id}. Recreating customer and retrying."
                )
                user.stripe_customer_id = None
                await db.commit()
                customer_id = await StripeService._ensure_stripe_customer_id(user, db)
                session = StripeService._create_checkout_session_payload(
                    customer_id=customer_id,
                    price_id=price_id,
                    user=user,
                    tier=tier,
                )
        except stripe.error.StripeError as exc:
            logger.error(
                f"Stripe API error creating checkout session for user {user.auth0_user_id}: {exc}"
            )
            message = getattr(exc, "user_message", None) or str(exc)
            raise ValueError(f"Stripe checkout error: {message}") from exc

        logger.info(f"Created checkout session {session.id} for user {user.auth0_user_id}")
        
        return {
            "url": session.url,
            "session_id": session.id,
        }

    @staticmethod
    async def create_portal_session(
        user: User,
        db: AsyncSession,
    ) -> Dict[str, str]:
        """
        Create a Stripe Customer Portal session for subscription management.
        
        Args:
            user: The user managing their subscription
            db: Database session
            
        Returns:
            Dictionary with portal session URL
        """
        if not settings.STRIPE_SECRET_KEY:
            raise ValueError("Stripe secret key is not configured")

        try:
            customer_id = await StripeService._ensure_stripe_customer_id(user, db)
            try:
                session = stripe.billing_portal.Session.create(
                    customer=customer_id,
                    return_url=f"{FRONTEND_URL}/profile",
                )
            except stripe.error.InvalidRequestError as exc:
                if not StripeService._is_missing_customer_error(exc):
                    raise
                logger.warning(
                    f"Stripe customer disappeared during portal session for user {user.auth0_user_id}: "
                    f"{customer_id}. Recreating customer and retrying."
                )
                user.stripe_customer_id = None
                await db.commit()
                customer_id = await StripeService._ensure_stripe_customer_id(user, db)
                session = stripe.billing_portal.Session.create(
                    customer=customer_id,
                    return_url=f"{FRONTEND_URL}/profile",
                )
        except stripe.error.StripeError as exc:
            logger.error(
                f"Stripe API error creating portal session for user {user.auth0_user_id}: {exc}"
            )
            message = getattr(exc, "user_message", None) or str(exc)
            raise ValueError(f"Stripe portal error: {message}") from exc

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
        if not STRIPE_WEBHOOK_SECRET:
            logger.error("STRIPE_WEBHOOK_SECRET is not configured")
            raise ValueError("Webhook secret not configured")

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

        user = await StripeService._find_user_by_customer_id(customer_id, db)
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
            for t, pid in _price_ids().items():
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

        # Confirm renewal by syncing user state directly from Stripe subscription.
        if subscription_id:
            try:
                subscription = stripe.Subscription.retrieve(subscription_id)
                await StripeService._update_user_subscription(subscription, db)
                return
            except Exception as exc:
                logger.error(
                    "Failed to sync subscription after successful payment "
                    f"(customer={customer_id}, subscription={subscription_id}): {exc}"
                )

        # Fallback: extend expiry from invoice line period end when subscription isn't available.
        user = await StripeService._find_user_by_customer_id(customer_id, db)
        if not user:
            logger.error(f"User not found for customer {customer_id}")
            return

        period_end = None
        lines = invoice.get("lines", {}).get("data", [])
        if lines and isinstance(lines, list):
            period_end = lines[0].get("period", {}).get("end")

        if period_end:
            user.subscription_expires_at = datetime.utcfromtimestamp(period_end)
            await db.commit()
            logger.info(
                f"Extended subscription expiry for user {user.auth0_user_id} "
                f"to {user.subscription_expires_at.isoformat()}"
            )

    @staticmethod
    async def _handle_payment_failed(invoice: Dict[str, Any], db: AsyncSession):
        """Handle failed payment."""
        customer_id = invoice.get("customer")
        subscription_id = invoice.get("subscription")
        logger.warning(f"Payment failed for customer {customer_id}, subscription {subscription_id}")

        user = await StripeService._find_user_by_customer_id(customer_id, db)
        if not user:
            logger.error(f"User not found for customer {customer_id}")
            return

        old_tier = user.subscription_tier
        user.subscription_tier = "free"
        user.subscription_expires_at = datetime.utcnow()
        if subscription_id:
            user.stripe_subscription_id = subscription_id

        await db.commit()
        logger.warning(
            f"Revoked paid access for user {user.auth0_user_id} after payment failure "
            f"(old_tier={old_tier}, new_tier={user.subscription_tier})"
        )

        # Notification hook: replace with real mail provider integration when available.
        if user.email:
            logger.warning(
                f"Billing notification required: payment failed for user {user.auth0_user_id} "
                f"({user.email}), subscription={subscription_id}"
            )
