# TickerStats

TickerStats is a full-stack investment research platform for student investment clubs. It combines real-time public-market data, relative valuation tables, deterministic DCF analysis, watchlists, saved searches, subscription-aware user accounts, and AI-assisted pitch deck generation.

The app is split into a React/Vite client and a FastAPI backend. Market data is sourced primarily from `yfinance`; authentication is handled with Auth0; persistence uses PostgreSQL; billing uses Stripe; and deck generation/export styling is powered by Gemini/Vertex plus the local PPTX renderer.

## Features

- Compare public companies across valuation, profitability, leverage, and market metrics.
- Add performance metrics such as return, volatility, and max drawdown over selectable periods.
- Run DCF target price calculations with auditable inputs and manual overrides.
- Generate investment pitch decks with modular sections such as overview, SWOT, valuation, catalysts, risks, governance, and sector analysis.
- Save watchlists, saved searches, and generated decks to a user account.
- Manage subscription tiers, usage limits, Stripe checkout, and admin workflows.
- Export comparison data for offline analysis.

## Tech Stack

**Frontend**

- React 18, TypeScript, Vite
- React Router, TanStack Query
- Auth0 React SDK
- Tailwind CSS
- Zod validation

**Backend**

- FastAPI, Pydantic v2, Uvicorn
- SQLAlchemy, Alembic, PostgreSQL
- yfinance, pandas, numpy
- Stripe
- LLM SDKs for deck generation
- ReportLab and OpenPyXL for export formats

## Repository Layout

```text
.
├── client/                  # React frontend
│   ├── src/
│   │   ├── api/             # API clients
│   │   ├── components/      # Shared UI and feature components
│   │   ├── hooks/           # React hooks
│   │   ├── pages/           # Route pages
│   │   ├── queries/         # TanStack Query hooks
│   │   ├── schemas/         # Zod schemas
│   │   ├── stores/          # Local persisted client state
│   │   └── routes.tsx       # Browser route configuration
│   └── package.json
├── server/                  # FastAPI backend
│   ├── app/
│   │   ├── api/             # Relative table, user, admin, Stripe routes
│   │   ├── core/            # Config, middleware, error handling
│   │   ├── deck/            # Deck generation API, services, sections
│   │   ├── models.py        # SQLAlchemy models
│   │   ├── schemas.py       # Shared Pydantic schemas
│   │   └── services/        # Shared business/data services
│   ├── alembic/             # Database migrations
│   ├── tests/               # Backend tests
│   ├── requirements.txt
│   └── run_unified.py
├── AUTH0_SETUP.md
├── SETUP_GUIDE.md
└── README.md
```

## Prerequisites

- Node.js 18+
- Python 3.11+
- PostgreSQL 15+ or Docker
- Auth0 tenant for protected app routes
- Optional: Stripe account for billing flows
- Optional: LLM provider API key for deck generation

## Local Setup

### 1. Clone and configure the backend

```bash
cd server
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Edit `server/.env` with your local values. At minimum, set:

```env
DATABASE_URL=postgresql://ticketstats:ticketstats@localhost:5432/ticketstats
ASYNC_DATABASE_URL=postgresql+asyncpg://ticketstats:ticketstats@localhost:5432/ticketstats
AUTH0_DOMAIN=your-tenant.us.auth0.com
AUTH0_API_AUDIENCE=https://api.tickerstats.com
DEBUG=True
ENVIRONMENT=development
```

For deck generation, also set an LLM key such as:

```env
GEMINI_API_KEY=your-key
```

### 2. Prepare the database

Create a local PostgreSQL database and user matching your connection strings, then run migrations:

```bash
cd server
alembic upgrade head
```

For a Docker-based local database and API container, see `server/docker-compose.yml` and `server/DOCKER_README.md`.

### 3. Start the backend

```bash
cd server
python run_unified.py
```

The API starts on `http://localhost:5000` by default.

Useful endpoints:

- `GET /health`
- `GET /docs`
- `GET /api/relative`
- `POST /api/v1/valuation/dcf`
- `POST /api/v1/deck/generate`

### 4. Configure and start the frontend

```bash
cd client
npm install
cp .env.example .env
npm run dev
```

Set the client environment variables:

```env
VITE_API_BASE=http://localhost:5000
VITE_AUTH0_DOMAIN=your-tenant.us.auth0.com
VITE_AUTH0_CLIENT_ID=your-auth0-client-id
VITE_AUTH0_AUDIENCE=https://api.tickerstats.com
VITE_STRIPE_CHECKOUT_URL=
```

The Vite dev server usually runs on `http://localhost:5173`.

## Auth0 Setup

The client and server both expect the same Auth0 API audience. For local development, configure your Auth0 SPA application with:

- Allowed Callback URLs: `http://localhost:5173, http://localhost:3000`
- Allowed Logout URLs: `http://localhost:5173, http://localhost:3000`
- Allowed Web Origins: `http://localhost:5173, http://localhost:3000`

See `AUTH0_SETUP.md` and `SETUP_GUIDE.md` for the full Auth0 walkthrough.

## Common Commands

Frontend:

```bash
cd client
npm run dev
npm run build
npm run lint
```

Backend:

```bash
cd server
python run_unified.py
pytest
alembic upgrade head
```

## API Overview

The backend mounts a single FastAPI application with these major areas:

- Relative table APIs for snapshot and performance metrics.
- DCF valuation APIs under `/api/v1/valuation`.
- Deck generation APIs under `/api/v1/deck`.
- User resources for watchlists, saved searches, and saved decks.
- Admin routes for account and usage management.
- Stripe checkout and webhook routes for subscription workflows.

Interactive API documentation is available at `http://localhost:5000/docs` when the backend is running.

## Notes for Contributors

- `client/src/routes.tsx` is the active frontend route map.
- `server/app/main.py` is the backend composition root.
- `server/app/deck/services/sections/` contains the modular pitch deck section implementations.
- Root setup docs are intentionally high level; deeper guides live in `client/README.md`, `server/README.md`, `SETUP_GUIDE.md`, and the deployment/admin docs under `server/`.

## License

MIT
