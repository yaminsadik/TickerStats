# Auth0 Configuration Guide

## Problem: Backend hanging when accessing Watchlist, Saved Searches, or Decks

If your backend seems to hang or run forever when accessing authenticated pages, this is likely due to incorrect Auth0 configuration.

## Root Cause

The `AUTH0_DOMAIN` in your `.env` files must be set to your **Auth0 tenant domain**, not your application domain.

### ❌ INCORRECT Configuration

```bash
# server/.env
AUTH0_DOMAIN=www.tickerstats.app  # WRONG - This is your app domain

# client/.env
VITE_AUTH0_DOMAIN=www.tickerstats.app  # WRONG
```

### ✅ CORRECT Configuration

```bash
# server/.env
AUTH0_DOMAIN=your-tenant.us.auth0.com  # Your actual Auth0 tenant

# client/.env
VITE_AUTH0_DOMAIN=your-tenant.us.auth0.com  # Same Auth0 tenant
```

## How to Find Your Auth0 Domain

1. Go to your [Auth0 Dashboard](https://manage.auth0.com/)
2. Navigate to **Applications** → Your Application
3. Look for the **Domain** field - it will look like:
   - `dev-xxxxx.us.auth0.com`
   - `your-tenant.eu.auth0.com`
   - `your-custom-domain.auth0.app`

## Step-by-Step Fix

### 1. Update Server Configuration

Edit `/home/syam/projects/ticketstats/server/.env`:

```bash
# Before (WRONG):
AUTH0_DOMAIN=www.tickerstats.app

# After (CORRECT - use YOUR actual Auth0 domain):
AUTH0_DOMAIN=dev-xxxxx.us.auth0.com
```

### 2. Update Client Configuration

Edit `/home/syam/projects/ticketstats/client/.env`:

```bash
# Before (WRONG):
VITE_AUTH0_DOMAIN=www.tickerstats.app

# After (CORRECT - same as server):
VITE_AUTH0_DOMAIN=dev-xxxxx.us.auth0.com
```

### 3. Restart Services

After updating the configuration files:

```bash
# Stop the backend server (Ctrl+C)
# Restart it:
cd server
source venv/bin/activate
python3 run_unified.py

# Restart the frontend (if running):
cd client
npm run dev
```

### 4. Verify the Fix

Test that the JWKS endpoint is accessible:

```bash
# Replace YOUR_AUTH0_DOMAIN with your actual domain
curl https://YOUR_AUTH0_DOMAIN/.well-known/jwks.json
```

This should return a JSON response with public keys, not hang or timeout.

## Why This Matters

When a user logs in via Auth0 and makes an authenticated request:

1. Frontend gets a JWT token from Auth0
2. Frontend sends the token to your backend
3. Backend verifies the token by fetching public keys from:
   ```
   https://{AUTH0_DOMAIN}/.well-known/jwks.json
   ```
4. If `AUTH0_DOMAIN` is wrong, this request hangs/fails
5. The entire API request hangs waiting for verification
6. Pages that need authentication (Watchlist, Saved Searches, Decks) appear to never load

## Additional Configuration

Make sure these are also set correctly:

### Backend (`server/.env`)
```bash
AUTH0_DOMAIN=your-tenant.us.auth0.com
AUTH0_API_AUDIENCE=https://api.tickerstats.com  # Your API identifier from Auth0
```

### Frontend (`client/.env`)
```bash
VITE_AUTH0_DOMAIN=your-tenant.us.auth0.com
VITE_AUTH0_CLIENT_ID=your-client-id  # From Auth0 Application settings
VITE_AUTH0_AUDIENCE=https://api.tickerstats.com  # Same as backend
```

## Testing Without Auth0

If you want to test the database functionality without Auth0, you can:

1. Temporarily bypass authentication by modifying the routes
2. Or set up a local Auth0 test tenant (free)
3. Or use mock authentication for development

For production use, proper Auth0 configuration is required.

## Need Help?

- Check your Auth0 Dashboard: https://manage.auth0.com/
- Auth0 Documentation: https://auth0.com/docs
- Verify your API settings in Auth0 Dashboard → Applications → APIs
