# TickerStats Client

React + TypeScript frontend for TickerStats - an investment research platform for student investment clubs.

## Features

### Core Functionality
- **Authentication**: Auth0 integration with protected routes
- **Browse/Compare**: Real-time relative valuation tables with yfinance data
- **Deck Generation**: AI-powered pitch deck creation using Gemini
- **Watchlists**: Save and track tickers with notes
- **Saved Searches**: Persist analysis configurations
- **User Profiles**: Subscription tiers, usage tracking, admin controls

### UI/UX
- **Responsive Design**: Tailwind CSS with custom design system
- **Dark Mode**: Slate color scheme optimized for readability
- **Real-time Updates**: TanStack Query for caching and optimistic updates
- **Smart Formatting**: Currency, percentage, and ratio formatting
- **CSV Export**: Download comparison data
- **Signal Indicators**: Visual cues for valuation metrics

## Prerequisites

- Node.js 18+
- npm or yarn
- Unified backend server running at `http://localhost:5000` (default)
- Auth0 account configured (see root `AUTH0_SETUP.md`)

## Setup

1. **Install dependencies:**
   ```bash
   cd client
   npm install
   ```

2. **Configure environment:**
   ```bash
   cp .env.example .env
   ```
   
   Update `.env` with your settings:
   ```bash
   VITE_API_BASE=http://localhost:5000
   VITE_AUTH0_DOMAIN=your-tenant.us.auth0.com
   VITE_AUTH0_AUDIENCE=https://api.tickerstats.com
   VITE_AUTH0_CLIENT_ID=your-client-id
   ```

3. **Start the development server:**
   ```bash
   npm run dev
   ```

4. **Open in browser:**
   Navigate to http://localhost:3000

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `VITE_API_BASE` | Yes | Backend API URL (default: `http://localhost:5000`) |
| `VITE_AUTH0_DOMAIN` | Yes | Auth0 tenant domain |
| `VITE_AUTH0_AUDIENCE` | Yes | Auth0 API identifier |
| `VITE_AUTH0_CLIENT_ID` | Yes | Auth0 application client ID |

## Usage Examples

### Browse Comparables
1. Navigate to `/browse`
2. Enter tickers: `AAPL MSFT NVDA GOOGL`
3. Select metrics to display
4. Sort by any column
5. Export to CSV

### Generate Pitch Deck
1. Navigate to `/deck/new`
2. Enter ticker and company info
3. Select deck sections (Overview, SWOT, Valuation, etc.)
4. Choose Gemini model quality level
5. Click **Generate Deck**
6. View/save generated slides

### Manage Watchlist
1. Go to `/watchlist`
2. Add tickers with optional notes
3. View all saved tickers
4. Update notes or remove entries

### Saved Searches
1. Run a comparison on `/browse`
2. Click **Save Search**
3. Access saved configurations from `/saved-searches`
4. Re-run or delete saved searches

## Tech Stack

- **Vite** - Fast build tool and dev server
- **React 18** - UI framework with hooks
- **TypeScript** - Type safety
- **React Router** - Client-side routing
- **TanStack Query** - Server state management and caching
- **Tailwind CSS** - Utility-first styling
- **Auth0 React SDK** - Authentication
- **Zod** - Runtime type validation
- **Radix UI** - Accessible component primitives
- **Lucide React** - Icon library

## Project Structure

```
client/
├── src/
│   ├── api/              # API client functions
│   │   ├── client.ts     # Authenticated fetch wrapper
│   │   ├── dcfApi.ts     # DCF valuation endpoints
│   │   ├── deckApi.ts    # Deck generation endpoints
│   │   ├── profileApi.ts # User profile endpoints
│   │   └── userApi.ts    # User resources (watchlist, searches, decks)
│   ├── components/       # Reusable UI components
│   │   ├── layout/       # Header, footer, navigation
│   │   ├── ui/           # Base UI primitives (Button, Input, etc.)
│   │   ├── Breadcrumbs.tsx
│   │   ├── ColumnPicker.tsx
│   │   ├── Controls.tsx
│   │   ├── ProtectedRoute.tsx
│   │   ├── RelativeTable.tsx
│   │   ├── SignalConfigDrawer.tsx
│   │   ├── TickerInput.tsx
│   │   └── ...modals
│   ├── hooks/            # Custom React hooks
│   │   ├── useAuthenticatedApi.ts
│   │   ├── useRelativeTable.ts
│   │   ├── useSignalSettings.ts
│   │   └── useUserProfile.ts
│   ├── lib/              # Utility libraries
│   │   ├── apiError.ts   # Error handling
│   │   ├── parse.ts      # Zod parsing helpers
│   │   └── queryKeys.ts  # TanStack Query key factory
│   ├── pages/            # Route components
│   │   ├── landing/      # Marketing pages
│   │   ├── AdminPage.tsx
│   │   ├── BrowsePage.tsx
│   │   ├── ContactPage.tsx
│   │   ├── DeckDraftPage.tsx
│   │   ├── DecksListPage.tsx
│   │   ├── DeckViewPage.tsx
│   │   ├── DeckWizardPage.tsx
│   │   ├── ProfilePage.tsx
│   │   ├── SavedSearchesPage.tsx
│   │   └── WatchlistPage.tsx
│   ├── queries/          # TanStack Query hooks
│   │   ├── useAdminQueries.ts
│   │   ├── useBrowseMutations.ts
│   │   ├── useDeckQueries.ts
│   │   ├── useProfileQuery.ts
│   │   ├── useSavedSearchQueries.ts
│   │   └── useWatchlistQueries.ts
│   ├── schemas/          # Zod validation schemas
│   │   ├── admin.ts
│   │   ├── deck.ts
│   │   ├── profile.ts
│   │   ├── relativeTable.ts
│   │   └── userResources.ts
│   ├── stores/           # Zustand state management
│   │   └── deckDraft.ts  # Local deck draft persistence
│   ├── styles/           # Design tokens
│   │   └── tokens.ts
│   ├── types/            # TypeScript type definitions
│   │   ├── api.ts
│   │   ├── dcf.ts
│   │   └── ...
│   ├── utils/            # Utility functions
│   ├── App.tsx           # Root component with Auth0Provider
│   ├── routes.tsx        # Route configuration
│   ├── main.tsx          # App entry point
│   └── index.css         # Global styles
├── public/               # Static assets
├── index.html
├── package.json
├── tailwind.config.js
├── tsconfig.json
└── vite.config.ts
```

## Scripts

| Command | Description |
|---------|-------------|
| `npm run dev` | Start development server |
| `npm run build` | Build for production |
| `npm run preview` | Preview production build |
| `npm run lint` | Run ESLint |

## License

MIT
