# TicketStats Client

A polished React frontend for the Investment Club Relative Table app.

## Features

- **Ticker Input**: Type or paste multiple tickers (supports comma, space, or newline separation)
- **Removable Chips**: Click X to remove individual tickers
- **Relative Table**: Dense, readable comparison table with sticky header and first column
- **Sorting**: Click any column header to sort (toggle asc/desc/none)
- **Column Selection**: Show/hide snapshot columns and performance metrics
- **Performance Metrics**: Toggle to include return, volatility, and max drawdown
- **Timeframe Selection**: Choose from 1mo to max periods for performance calculations
- **CSV Export**: Download current table data as CSV
- **Smart Formatting**: Currency, percentage, and ratio formatting based on data type

## Prerequisites

- Node.js 18+
- npm or yarn
- Backend server running at `http://localhost:8000` (or configure via env)

## Setup

1. **Install dependencies:**
   ```bash
   cd client
   npm install
   ```

2. **Configure environment (optional):**
   ```bash
   cp .env.example .env
   # Edit .env to change API base URL if needed
   ```

3. **Start the development server:**
   ```bash
   npm run dev
   ```

4. **Open in browser:**
   The app will open automatically at http://localhost:3000

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `VITE_API_BASE` | `http://localhost:8000` | Backend API base URL |

## Usage Examples

### Basic Comparison
1. Type tickers in the input: `AAPL MSFT NVDA GOOGL`
2. Click **Compare**
3. View the relative table with all metrics

### With Performance Metrics
1. Enter tickers: `AAPL, MSFT, TSLA`
2. Toggle **Include Performance** ON
3. Select timeframe: `3 Months`
4. Click **Compare**
5. Table now shows return, volatility, and max drawdown

### Custom Columns
1. Click **Show Column Settings**
2. Uncheck columns you don't need (e.g., hide evRevenue, debtEquity)
3. The table updates immediately

### Export Data
1. After viewing data, click **Export CSV**
2. CSV file downloads with current columns and symbols

## Tech Stack

- **Vite** - Fast build tool
- **React 18** - UI framework
- **TypeScript** - Type safety
- **Tailwind CSS** - Styling
- **TanStack Query** - Data fetching and caching

## Project Structure

```
client/
├── src/
│   ├── api/
│   │   └── client.ts       # API client functions
│   ├── components/
│   │   ├── ColumnPicker.tsx
│   │   ├── Controls.tsx
│   │   ├── RelativeTable.tsx
│   │   └── TickerInput.tsx
│   ├── hooks/
│   │   └── useRelativeTable.ts
│   ├── types/
│   │   └── api.ts          # TypeScript types
│   ├── utils/
│   │   └── formatters.ts   # Number formatting
│   ├── App.tsx
│   ├── index.css
│   └── main.tsx
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
