# Admin User Management

This guide explains the admin system in TicketStats, how to grant/revoke admin access, and what permissions admins receive.

## What is Admin Access?

Admin users have special privileges that bypass normal usage limits and restrictions:

✅ **Unlimited API Usage** - No rate limiting on API endpoints  
✅ **Unlimited Deck Generation** - Create as many decks as needed (bypasses monthly limits)  
✅ **Unlimited Comparisons** - No monthly comparison limits (free users: 5/month, pro: 100/month)  
✅ **Admin-Only Endpoints** - Access to user management and admin API routes  
✅ **Testing & Development** - Ideal for developers and internal testing

### Technical Details

- Admin status is stored in the `users` table as the `is_admin` boolean column
- Usage limit checks automatically skip admins (see `app/services/usage_limits.py`)
- Admin flag works independently of subscription tier (free/pro/enterprise)
- Admins are identified by the `is_admin` flag, not subscription tier

## Prerequisites

Before managing admin users:

1. **Database must be running**

   ```bash
   # For Docker database
   cd server
   docker-compose up -d db

   # For local PostgreSQL
   systemctl status postgresql
   ```

2. **User must exist in database**
   - User must have logged in via Auth0 at least once
   - This creates their database record automatically

3. **Virtual environment activated**
   ```bash
   source venv/bin/activate
   ```

## Grant Admin Access

### Method 1: Using update_users.py Script (Recommended)

```bash
cd server
source venv/bin/activate
python update_users.py admin user@example.com true
```

**Example:**

```bash
python update_users.py admin yaminsadik.sy@gmail.com true
```

**Output:**

```
🔐 Updating admin status for: yaminsadik.sy@gmail.com
   Auth0 ID: auth0|1234567890
   Name: Yamin Sadik
   Status: Regular User → Admin

✅ Admin status updated successfully!

🎉 yaminsadik.sy@gmail.com now has unlimited access to all features!
```

### Method 2: Direct SQL

```bash
# Connect to database
psql -U postgres -d ticketstats -h localhost

# Grant admin access
UPDATE users
SET is_admin = true, updated_at = NOW()
WHERE email = 'user@example.com';

# Verify the change
SELECT email, is_admin, subscription_tier FROM users WHERE email = 'user@example.com';
```

### Method 3: Database GUI Tool

Use pgAdmin, DBeaver, TablePlus, or any PostgreSQL client:

1. Connect to the database
2. Navigate to `ticketstats` database → `users` table
3. Find the user by email
4. Set `is_admin` column to `true`
5. Update `updated_at` to current timestamp

## Revoke Admin Access

### Using update_users.py Script

```bash
cd server
source venv/bin/activate
python update_users.py admin user@example.com false
```

**Output:**

```
🔐 Updating admin status for: user@example.com
   Auth0 ID: auth0|1234567890
   Name: User Name
   Status: Admin → Regular User

✅ Admin status updated successfully!
```

### Using SQL

```sql
UPDATE users
SET is_admin = false, updated_at = NOW()
WHERE email = 'user@example.com';
```

## List All Users

View all users and their admin status:

```bash
python update_users.py list
```

**Example Output:**

```
==============================================================================================================
Auth0 User ID                            Email                          Name                 Tier       Admin
==============================================================================================================
auth0|1234567890                         yaminsadik.sy@gmail.com        Yamin Sadik          free       ✅
auth0|0987654321                         test@example.com               Test User            pro
==============================================================================================================

Total users: 2
Admin users: 1
```

## Update User Script Commands

The `update_users.py` script supports multiple commands:

### List all users

```bash
python update_users.py list
```

### Update user info

```bash
python update_users.py update <auth0_id> <email> <name>
```

### Grant/revoke admin

```bash
python update_users.py admin <email> <true|false>
```

### Sync from Auth0

```bash
export AUTH0_MANAGEMENT_TOKEN='your_token'
python update_users.py sync
```

## How Admin Rights Work

### Code Implementation

The admin check is implemented in `app/services/usage_limits.py`:

```python
def get_plan_tier(user: User) -> str:
    if user.is_admin:
        return "enterprise"  # Admins treated as enterprise tier
    # ... rest of logic
```

### Bypass Points

Admin users bypass limits at:

1. **Comparison Limits** - No monthly limit on comparison requests
2. **Deck Generation** - Unlimited deck creation
3. **Rate Limiting** - No API throttling
4. **Feature Flags** - Access to beta/experimental features

### API Route Protection

Admin-only routes use the `require_admin` dependency:

```python
from app.core.auth import require_admin

@router.get("/admin/users")
async def get_all_users(current_user: User = Depends(require_admin)):
    # Only admins can access this
    pass
```

## Troubleshooting

### "User not found with email"

**Problem:** User hasn't logged in yet via Auth0

**Solution:**

1. Have user log in to the app first
2. This creates their database record
3. Then grant admin access

### Database Connection Errors

**Problem:** `asyncpg.exceptions.InvalidPasswordError` or connection refused

**Solutions:**

1. **Check database is running:**

   ```bash
   docker ps  # Should show postgres container
   docker-compose up -d db  # Start if not running
   ```

2. **Verify credentials in .env:**

   ```bash
   # For Docker database, use:
   DATABASE_URL=postgresql://postgres:postgres@localhost:5432/ticketstats
   ASYNC_DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/ticketstats
   ```

3. **Port conflict (5432 already in use):**

   ```bash
   # Stop local PostgreSQL if running
   sudo systemctl stop postgresql

   # Or use different port in docker-compose.yml
   ports:
     - "127.0.0.1:5433:5432"
   ```

### Script Exits with Code 1

Check the full error output:

```bash
cd server
source venv/bin/activate
python update_users.py list 2>&1 | tail -20
```

Common issues:

- Database not running
- Wrong credentials in `.env`
- Port already in use
- Missing database tables (run migrations)

## Security Best Practices

1. **Limit admin users** - Only grant to trusted developers/staff
2. **Audit regularly** - Use `python update_users.py list` to review admins
3. **Revoke when leaving** - Remove admin access when team members leave
4. **Use production secrets** - Don't commit `.env` with real credentials
5. **Monitor admin actions** - Check `admin_audit_log` table for changes

## Database Schema

The `users` table structure:

```sql
CREATE TABLE users (
    auth0_user_id VARCHAR(255) PRIMARY KEY,
    email VARCHAR(255) UNIQUE,
    name VARCHAR(255),
    picture TEXT,
    subscription_tier VARCHAR(20) DEFAULT 'free',
    is_admin BOOLEAN NOT NULL DEFAULT FALSE,
    stripe_customer_id VARCHAR(255),
    stripe_subscription_id VARCHAR(255),
    subscription_expires_at TIMESTAMP,
    usage_month_start TIMESTAMP,
    deck_count_month INTEGER DEFAULT 0,
    compare_count_month INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

## Related Files

- `server/update_users.py` - User management script
- `server/app/models.py` - User model definition
- `server/app/services/usage_limits.py` - Usage limit logic
- `server/app/core/auth.py` - Auth dependencies including `require_admin`
- `server/app/api/routes_user.py` - Admin API endpoints

## Additional Resources

- [Server README](README.md) - General server setup
- [Auth0 Setup](AUTH0_SETUP.md) - Auth0 configuration
- [Docker README](DOCKER_README.md) - Docker deployment guide
