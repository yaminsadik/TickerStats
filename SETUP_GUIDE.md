# TicketStats Setup Guide

## Prerequisites

1. **PostgreSQL** installed and running
2. **Auth0 Account** - Sign up at [auth0.com](https://auth0.com)
3. **Node.js** 18+ and **Python** 3.11+

---

## Step 1: Database Setup

### Install PostgreSQL

**Ubuntu/Debian:**

```bash
sudo apt update
sudo apt install postgresql postgresql-contrib
sudo systemctl start postgresql
```

**macOS:**

```bash
brew install postgresql@15
brew services start postgresql@15
```

### Create Database and User

```bash
sudo -u postgres psql

# In PostgreSQL shell:
CREATE DATABASE ticketstats;
CREATE USER ticketstats WITH PASSWORD 'ticketstats';
GRANT ALL PRIVILEGES ON DATABASE ticketstats TO ticketstats;
\q
```

---

## Step 2: Auth0 Configuration

### Create Auth0 API

1. Go to [Auth0 Dashboard](https://manage.auth0.com)
2. Navigate to **Applications > APIs > Create API**
3. Fill in:
   - **Name**: TicketStats API
   - **Identifier**: `https://api.ticketstats.com` (use this exact value)
   - **Signing Algorithm**: RS256
4. Click **Create**
5. Copy the **Identifier** - this is your `AUTH0_API_AUDIENCE`

### Create Auth0 Application (SPA)

1. Navigate to **Applications > Applications > Create Application**
2. Fill in:
   - **Name**: TicketStats Client
   - **Application Type**: Single Page Web Applications
3. Click **Create**
4. Go to **Settings** tab
5. Configure:
   - **Allowed Callback URLs**: `http://localhost:5173, http://localhost:3000`
   - **Allowed Logout URLs**: `http://localhost:5173, http://localhost:3000`
   - **Allowed Web Origins**: `http://localhost:5173, http://localhost:3000`
6. Click **Save Changes**
7. Copy:
   - **Domain** (e.g., `your-tenant.us.auth0.com`)
   - **Client ID**

---

## Step 3: Backend Setup

### Install Dependencies

```bash
cd server
pip install -r requirements.txt
```

### Configure Environment

```bash
cp .env.example .env
```

Edit `.env` and fill in:

```env
DATABASE_URL=postgresql://ticketstats:ticketstats@localhost:5432/ticketstats
ASYNC_DATABASE_URL=postgresql+asyncpg://ticketstats:ticketstats@localhost:5432/ticketstats

AUTH0_DOMAIN=your-tenant.us.auth0.com
AUTH0_API_AUDIENCE=https://api.ticketstats.com

DEBUG=True
ENVIRONMENT=development
```

### Run Database Migrations

```bash
# Generate initial migration
alembic revision --autogenerate -m "Initial schema"

# Apply migration
alembic upgrade head
```

### Start Backend Server

```bash
# FastAPI server (port 8000)
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Flask Deck Service (port 5001) - in separate terminal
python run_unified.py
```

---

## Step 4: Frontend Setup

### Install Dependencies

```bash
cd client
npm install
```

### Configure Environment

```bash
cp .env.example .env
```

Edit `.env` and fill in:

```env
VITE_API_BASE_URL=http://localhost:8000

VITE_AUTH0_DOMAIN=your-tenant.us.auth0.com
VITE_AUTH0_CLIENT_ID=your-auth0-client-id
VITE_AUTH0_AUDIENCE=https://api.ticketstats.com
```

### Start Frontend

```bash
npm run dev
```

Visit: http://localhost:5173

---

## Step 5: Verify Setup

### Test Authentication

1. Open http://localhost:5173
2. Click **Login** button (top right)
3. Sign up/login with Auth0
4. You should be redirected back with your name displayed

### Test Protected API

Open browser console and run:

```javascript
// Get access token
const token = localStorage.getItem(
  "@@auth0spajs@@::YOUR_CLIENT_ID::https://api.ticketstats.com::openid profile email",
);

// Make authenticated request
fetch("http://localhost:8000/api/user/watchlist", {
  headers: {
    Authorization: `Bearer ${token}`,
  },
})
  .then((r) => r.json())
  .then(console.log);
```

You should see an empty watchlist `[]`.

---

## Database Models

The following tables are created:

### `users`

- `auth0_user_id` (PK) - Auth0 user ID
- `email` - User email
- `name` - User display name
- `created_at`, `updated_at`

### `watchlists`

- `id` (PK)
- `user_id` (FK to users)
- `ticker` - Stock symbol
- `notes` - User notes
- `created_at`

### `saved_analyses`

- `id` (PK)
- `user_id` (FK to users)
- `name`, `description`
- `symbols` (JSON) - List of tickers
- `snapshot_fields` (JSON)
- `perf_periods` (JSON)
- `include_dcf` (Boolean)
- `created_at`, `updated_at`

### `decks`

- `id` (PK)
- `user_id` (FK to users)
- `ticker`
- `title`
- `content` (JSON) - Full deck data
- `llm_provider`
- `created_at`

---

## API Endpoints

### Public Endpoints (No Auth Required)

- `GET /api/relative` - Relative table data
- `GET /api/dcf/{ticker}` - DCF valuation
- `GET /docs` - API documentation

### Protected Endpoints (Requires Auth0 JWT)

- `GET /api/user/watchlist` - Get watchlist
- `POST /api/user/watchlist` - Add to watchlist
- `DELETE /api/user/watchlist/{ticker}` - Remove from watchlist
- `GET /api/user/analyses` - Get saved analyses
- `POST /api/user/analyses` - Save new analysis
- `DELETE /api/user/analyses/{id}` - Delete analysis
- `GET /api/user/decks` - Get generated decks
- `GET /api/user/decks/{id}` - Get specific deck

---

## Troubleshooting

### "Invalid token" error

- Verify `AUTH0_DOMAIN` and `AUTH0_API_AUDIENCE` match in both frontend and backend `.env` files
- Check Auth0 API settings: Signing Algorithm must be RS256

### Database connection error

- Ensure PostgreSQL is running: `sudo systemctl status postgresql`
- Test connection: `psql -U ticketstats -d ticketstats -h localhost`

### CORS errors

- Backend CORS is set to allow all origins (`allow_origins=["*"]`)
- For production, update in `server/app/main.py`

### Migration errors

```bash
# Reset database (WARNING: deletes all data)
alembic downgrade base
alembic upgrade head
```

---

## Next Steps

1. **Add email extraction**: Update `app/core/auth.py` to parse email from JWT claims
2. **Implement saved analyses UI**: Create page to list/load saved analyses
3. **Add watchlist UI**: Create watchlist management page
4. **Protect deck generation**: Require auth for deck endpoints
5. **Production deployment**:
   - Use managed PostgreSQL (AWS RDS, Supabase)
   - Configure proper CORS origins
   - Enable Auth0 production mode

---

## Production Checklist

- [ ] Change database credentials
- [ ] Update Auth0 callback URLs to production domain
- [ ] Set `DEBUG=False` in backend
- [ ] Configure proper CORS origins (not `*`)
- [ ] Enable HTTPS/TLS
- [ ] Set up database backups
- [ ] Add rate limiting (Redis + FastAPI-Limiter)
- [ ] Monitor Auth0 usage (free tier: 7,000 active users)
- [ ] Add logging and error tracking (Sentry)
