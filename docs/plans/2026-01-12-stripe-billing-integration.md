# Stripe Billing Integration - Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add Stripe subscription billing to enable paid Pro ($29/mo) and Enterprise ($99/mo) tiers.

**Architecture:** Use Stripe Checkout for payment, webhooks for subscription events, and store subscription status in the database. The existing `subscriptions.py` module defines tier limits.

**Tech Stack:** Stripe Python SDK, FastAPI webhooks, SQLAlchemy for persistence

---

## Prerequisites

Before starting:
1. Create Stripe account at dashboard.stripe.com
2. Get API keys (test mode first)
3. Create products and prices in Stripe dashboard:
   - Pro: $29/month (price_pro_monthly)
   - Enterprise: $99/month (price_enterprise_monthly)

---

## Task 1: Add Stripe Dependency

**Files:**
- Modify: `requirements.txt`

**Step 1: Add stripe to requirements**

```
# In requirements.txt, add:
stripe==7.10.0
```

**Step 2: Install dependencies**

Run: `pip install stripe==7.10.0`
Expected: Successful installation

**Step 3: Commit**

```bash
git add requirements.txt
git commit -m "chore: add stripe dependency"
```

---

## Task 2: Add Stripe Configuration

**Files:**
- Modify: `src/config.py`

**Step 1: Write failing test**

Create: `tests/test_stripe_config.py`

```python
import pytest
from src.config import settings

def test_stripe_settings_exist():
    """Stripe configuration should be available."""
    assert hasattr(settings, 'STRIPE_SECRET_KEY')
    assert hasattr(settings, 'STRIPE_PUBLISHABLE_KEY')
    assert hasattr(settings, 'STRIPE_WEBHOOK_SECRET')
    assert hasattr(settings, 'STRIPE_PRO_PRICE_ID')
    assert hasattr(settings, 'STRIPE_ENTERPRISE_PRICE_ID')
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_stripe_config.py -v`
Expected: FAIL - AttributeError

**Step 3: Add Stripe settings to config.py**

```python
# Add to Settings class in src/config.py:

    # ============================================
    # STRIPE BILLING
    # ============================================
    STRIPE_SECRET_KEY: Optional[str] = None
    STRIPE_PUBLISHABLE_KEY: Optional[str] = None
    STRIPE_WEBHOOK_SECRET: Optional[str] = None
    STRIPE_PRO_PRICE_ID: str = "price_pro_monthly"
    STRIPE_ENTERPRISE_PRICE_ID: str = "price_enterprise_monthly"
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_stripe_config.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/config.py tests/test_stripe_config.py
git commit -m "feat: add stripe configuration settings"
```

---

## Task 3: Create Stripe Service Module

**Files:**
- Create: `src/stripe_service.py`
- Create: `tests/test_stripe_service.py`

**Step 1: Write failing test**

```python
# tests/test_stripe_service.py
import pytest
from src.stripe_service import StripeService

def test_stripe_service_initializes():
    """StripeService should initialize with API key."""
    service = StripeService(api_key="sk_test_fake")
    assert service is not None
    assert service.api_key == "sk_test_fake"

def test_create_checkout_session_url_format():
    """create_checkout_session should return proper URL structure."""
    service = StripeService(api_key="sk_test_fake")
    # This will fail until implemented
    result = service.create_checkout_session(
        customer_email="test@example.com",
        price_id="price_pro",
        success_url="https://example.com/success",
        cancel_url="https://example.com/cancel"
    )
    assert "url" in result or "error" in result
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_stripe_service.py -v`
Expected: FAIL - ModuleNotFoundError

**Step 3: Implement StripeService**

```python
# src/stripe_service.py
"""
Stripe Service Module

Handles all Stripe API interactions:
- Checkout session creation
- Subscription management
- Webhook processing
"""
import stripe
from typing import Optional, Dict, Any
from loguru import logger
from dataclasses import dataclass

from .config import settings


@dataclass
class CheckoutResult:
    """Result of checkout session creation."""
    success: bool
    url: Optional[str] = None
    session_id: Optional[str] = None
    error: Optional[str] = None


class StripeService:
    """
    Service for Stripe billing operations.

    Usage:
        service = StripeService()
        result = service.create_checkout_session(
            customer_email="user@example.com",
            price_id=settings.STRIPE_PRO_PRICE_ID,
            success_url="https://app.com/success",
            cancel_url="https://app.com/cancel"
        )
    """

    def __init__(self, api_key: str = None):
        self.api_key = api_key or settings.STRIPE_SECRET_KEY
        if self.api_key:
            stripe.api_key = self.api_key

    def create_checkout_session(
        self,
        customer_email: str,
        price_id: str,
        success_url: str,
        cancel_url: str,
        metadata: Dict[str, str] = None
    ) -> Dict[str, Any]:
        """
        Create a Stripe Checkout session for subscription.

        Returns dict with 'url' on success or 'error' on failure.
        """
        if not self.api_key:
            return {"error": "Stripe API key not configured"}

        try:
            session = stripe.checkout.Session.create(
                customer_email=customer_email,
                payment_method_types=["card"],
                line_items=[{
                    "price": price_id,
                    "quantity": 1
                }],
                mode="subscription",
                success_url=success_url + "?session_id={CHECKOUT_SESSION_ID}",
                cancel_url=cancel_url,
                metadata=metadata or {}
            )

            logger.info(f"Created checkout session for {customer_email}")
            return {
                "url": session.url,
                "session_id": session.id
            }

        except stripe.error.StripeError as e:
            logger.error(f"Stripe error: {e}")
            return {"error": str(e)}

    def get_subscription(self, subscription_id: str) -> Optional[Dict]:
        """Get subscription details from Stripe."""
        if not self.api_key:
            return None

        try:
            subscription = stripe.Subscription.retrieve(subscription_id)
            return {
                "id": subscription.id,
                "status": subscription.status,
                "current_period_end": subscription.current_period_end,
                "cancel_at_period_end": subscription.cancel_at_period_end,
                "price_id": subscription.items.data[0].price.id
            }
        except stripe.error.StripeError as e:
            logger.error(f"Error fetching subscription: {e}")
            return None

    def cancel_subscription(self, subscription_id: str, at_period_end: bool = True) -> bool:
        """
        Cancel a subscription.

        Args:
            subscription_id: Stripe subscription ID
            at_period_end: If True, cancel at end of billing period
        """
        if not self.api_key:
            return False

        try:
            if at_period_end:
                stripe.Subscription.modify(
                    subscription_id,
                    cancel_at_period_end=True
                )
            else:
                stripe.Subscription.delete(subscription_id)

            logger.info(f"Cancelled subscription {subscription_id}")
            return True

        except stripe.error.StripeError as e:
            logger.error(f"Error cancelling subscription: {e}")
            return False

    def construct_webhook_event(self, payload: bytes, sig_header: str) -> Optional[Any]:
        """
        Construct and verify a webhook event.

        Args:
            payload: Raw request body
            sig_header: Stripe-Signature header
        """
        webhook_secret = settings.STRIPE_WEBHOOK_SECRET
        if not webhook_secret:
            logger.error("Webhook secret not configured")
            return None

        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, webhook_secret
            )
            return event
        except ValueError as e:
            logger.error(f"Invalid payload: {e}")
            return None
        except stripe.error.SignatureVerificationError as e:
            logger.error(f"Invalid signature: {e}")
            return None
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_stripe_service.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/stripe_service.py tests/test_stripe_service.py
git commit -m "feat: add stripe service module"
```

---

## Task 4: Add Billing API Endpoints

**Files:**
- Modify: `src/main.py`
- Create: `tests/test_billing_endpoints.py`

**Step 1: Write failing test**

```python
# tests/test_billing_endpoints.py
import pytest
from fastapi.testclient import TestClient
from src.main import app

client = TestClient(app)

def test_create_checkout_endpoint_exists():
    """POST /billing/checkout should exist."""
    response = client.post("/billing/checkout", json={
        "email": "test@example.com",
        "tier": "pro"
    })
    # Should not be 404
    assert response.status_code != 404

def test_webhook_endpoint_exists():
    """POST /billing/webhook should exist."""
    response = client.post("/billing/webhook", content=b"test")
    # Should not be 404 (may be 400 due to invalid signature)
    assert response.status_code != 404
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_billing_endpoints.py -v`
Expected: FAIL - 404 Not Found

**Step 3: Add billing endpoints to main.py**

```python
# Add to src/main.py after existing endpoints:

from .stripe_service import StripeService
from .subscriptions import SubscriptionManager, SubscriptionTier

# Initialize services
stripe_service = StripeService()
subscription_manager = SubscriptionManager()

# =========================================
# BILLING ENDPOINTS
# =========================================

class CheckoutRequest(BaseModel):
    email: str
    tier: str  # "pro" or "enterprise"

class CheckoutResponse(BaseModel):
    url: Optional[str] = None
    error: Optional[str] = None

@app.post("/billing/checkout", response_model=CheckoutResponse)
async def create_checkout(request: CheckoutRequest):
    """
    Create a Stripe Checkout session for subscription.

    Returns a URL to redirect the user to Stripe's hosted checkout.
    """
    # Determine price ID based on tier
    if request.tier == "pro":
        price_id = settings.STRIPE_PRO_PRICE_ID
    elif request.tier == "enterprise":
        price_id = settings.STRIPE_ENTERPRISE_PRICE_ID
    else:
        return CheckoutResponse(error=f"Invalid tier: {request.tier}")

    result = stripe_service.create_checkout_session(
        customer_email=request.email,
        price_id=price_id,
        success_url=f"{settings.FRONTEND_URL}/billing/success",
        cancel_url=f"{settings.FRONTEND_URL}/billing/cancel",
        metadata={"tier": request.tier}
    )

    if "error" in result:
        return CheckoutResponse(error=result["error"])

    return CheckoutResponse(url=result["url"])


@app.post("/billing/webhook")
async def stripe_webhook(request: Request):
    """
    Handle Stripe webhook events.

    Events handled:
    - checkout.session.completed: New subscription created
    - customer.subscription.updated: Subscription changed
    - customer.subscription.deleted: Subscription cancelled
    """
    payload = await request.body()
    sig_header = request.headers.get("Stripe-Signature", "")

    event = stripe_service.construct_webhook_event(payload, sig_header)
    if not event:
        raise HTTPException(status_code=400, detail="Invalid webhook")

    event_type = event["type"]
    data = event["data"]["object"]

    logger.info(f"Received Stripe webhook: {event_type}")

    if event_type == "checkout.session.completed":
        # New subscription created
        customer_email = data.get("customer_email")
        subscription_id = data.get("subscription")
        tier = data.get("metadata", {}).get("tier", "pro")

        # Update subscriber in our system
        subscriber = subscription_manager.get_subscriber_by_email(customer_email)
        if not subscriber:
            subscriber = subscription_manager.create_subscriber(customer_email)

        new_tier = SubscriptionTier.PRO if tier == "pro" else SubscriptionTier.ENTERPRISE
        subscription_manager.update_tier(subscriber.id, new_tier)
        subscriber.stripe_customer_id = data.get("customer")

        logger.info(f"Activated {tier} subscription for {customer_email}")

    elif event_type == "customer.subscription.deleted":
        # Subscription cancelled
        customer_id = data.get("customer")
        # Find and downgrade subscriber
        for sub in subscription_manager._subscribers.values():
            if sub.stripe_customer_id == customer_id:
                subscription_manager.update_tier(sub.id, SubscriptionTier.FREE)
                logger.info(f"Downgraded {sub.email} to free tier")
                break

    return {"status": "ok"}


@app.get("/billing/subscription/{subscriber_id}")
async def get_subscription_status(subscriber_id: str):
    """Get current subscription status for a subscriber."""
    subscriber = subscription_manager.get_subscriber(subscriber_id)
    if not subscriber:
        raise HTTPException(status_code=404, detail="Subscriber not found")

    return {
        "id": subscriber.id,
        "email": subscriber.email,
        "tier": subscriber.tier.value,
        "is_active": subscriber.is_active,
        "limits": {
            "alerts_per_day": subscriber.limits.max_alerts_per_day,
            "tracked_wallets": subscriber.limits.max_tracked_wallets,
            "real_time_alerts": subscriber.limits.real_time_alerts,
            "smart_money_access": subscriber.limits.smart_money_access,
            "api_access": subscriber.limits.api_access
        }
    }
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_billing_endpoints.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/main.py tests/test_billing_endpoints.py
git commit -m "feat: add billing API endpoints for Stripe checkout"
```

---

## Task 5: Update .env.example with Stripe Variables

**Files:**
- Modify: `.env.example`

**Step 1: Add Stripe environment variables**

```bash
# Add to .env.example:

# ============================================================
# 💳 STRIPE BILLING
# ============================================================
# Get keys from dashboard.stripe.com/apikeys
# STRIPE_SECRET_KEY=sk_test_xxxxx
# STRIPE_PUBLISHABLE_KEY=pk_test_xxxxx

# Webhook secret from dashboard.stripe.com/webhooks
# STRIPE_WEBHOOK_SECRET=whsec_xxxxx

# Price IDs from your Stripe products
# STRIPE_PRO_PRICE_ID=price_xxxxx
# STRIPE_ENTERPRISE_PRICE_ID=price_xxxxx
```

**Step 2: Commit**

```bash
git add .env.example
git commit -m "docs: add stripe environment variables to .env.example"
```

---

## Task 6: Integration Test

**Files:**
- Create: `tests/test_billing_integration.py`

**Step 1: Write integration test**

```python
# tests/test_billing_integration.py
"""
Integration tests for billing flow.
Uses Stripe test mode.
"""
import pytest
from src.stripe_service import StripeService
from src.subscriptions import SubscriptionManager, SubscriptionTier

class TestBillingIntegration:
    """End-to-end billing tests."""

    def test_subscription_tier_upgrade_flow(self):
        """Test complete flow: free -> checkout -> pro."""
        manager = SubscriptionManager()

        # Start as free user
        subscriber = manager.create_subscriber("test@example.com")
        assert subscriber.tier == SubscriptionTier.FREE

        # Simulate successful payment (webhook would do this)
        manager.update_tier(subscriber.id, SubscriptionTier.PRO, duration_days=30)

        # Verify upgrade
        updated = manager.get_subscriber(subscriber.id)
        assert updated.tier == SubscriptionTier.PRO
        assert updated.is_active == True
        assert updated.limits.real_time_alerts == True

    def test_subscription_downgrade_on_cancel(self):
        """Test downgrade to free when subscription cancelled."""
        manager = SubscriptionManager()

        # Start as pro user
        subscriber = manager.create_subscriber("pro@example.com")
        manager.update_tier(subscriber.id, SubscriptionTier.PRO)

        # Cancel (downgrade to free)
        manager.update_tier(subscriber.id, SubscriptionTier.FREE)

        # Verify downgrade
        updated = manager.get_subscriber(subscriber.id)
        assert updated.tier == SubscriptionTier.FREE
        assert updated.limits.real_time_alerts == False
```

**Step 2: Run integration tests**

Run: `pytest tests/test_billing_integration.py -v`
Expected: PASS

**Step 3: Commit**

```bash
git add tests/test_billing_integration.py
git commit -m "test: add billing integration tests"
```

---

## Verification Checklist

Before marking complete:

- [ ] Stripe SDK installed and imported
- [ ] Configuration variables added
- [ ] StripeService class implemented
- [ ] Checkout endpoint working
- [ ] Webhook endpoint working
- [ ] Subscription status endpoint working
- [ ] All tests passing
- [ ] .env.example updated

---

## Next Steps After Implementation

1. **Set up Stripe Dashboard:**
   - Create Pro and Enterprise products/prices
   - Configure webhook endpoint URL
   - Enable test mode webhooks

2. **Frontend Integration:**
   - Add checkout button to dashboard
   - Handle success/cancel redirects
   - Show subscription status in UI

3. **Production Deployment:**
   - Switch to live API keys
   - Configure production webhook URL
   - Test with real payments
