# TicketStats API

A production-lean FastAPI backend that powers a "relative table" for student investment clubs using yfinance.

## Features

- **Snapshot Metrics**: Fetch fundamentals/valuation metrics for multiple tickers
- **Performance Metrics**: Compute timeframe-based performance (return, volatility, max drawdown)
- **Batch Processing**: Support for up to 30 tickers per request
- **In-Memory Caching**: TTLCache with 120s TTL for both snapshot and performance data
- **CSV Export**: Export table data to CSV format
- **Concurrent Fetching**: ThreadPoolExecutor for parallel yfinance requests

## Project Structure

```
server/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI app entry point
│   ├── schemas.py           # Pydantic v2 models
│   ├── api/
│   │   ├── __init__.py
│   │   └── routes.py        # API route handlers
│   ├── core/
│   │   ├── __init__.py
│   │   └── config.py        # Configuration constants
│   └── services/
│       ├── __init__.py
│       └── yfinance_service.py  # YFinance data service
├── requirements.txt
└── README.md
```

## Setup Instructions

### Prerequisites

- Python 3.11+

### Installation

1. Navigate to the server directory:
   ```bash
   cd server
   ```

2. Create a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

### Running the Server

```bash
uvicorn app.main:app --reload
```

The server will start at `http://localhost:8000`.

### API Documentation

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## API Endpoints

### 1. Health Check

```bash
curl http://localhost:8000/health
```

Response:
```json
{"status": "ok"}
```

### 2. Relative Table (Snapshot Only)

Fetch snapshot metrics for multiple symbols:

```bash
curl "http://localhost:8000/api/relative?symbols=AAPL,MSFT,NVDA"
```

With specific fields:

```bash
curl "http://localhost:8000/api/relative?symbols=AAPL,MSFT&fields=sharePrice,marketCap,forwardPE,beta"
```

### 3. Relative Table (With Performance)

Fetch snapshot and performance metrics:

```bash
curl "http://localhost:8000/api/relative?symbols=AAPL,MSFT,NVDA&perf=return,volatility,maxDrawdown&perfPeriod=3mo"
```

### 4. CSV Export

Export data as CSV:

```bash
curl "http://localhost:8000/api/relative/export?symbols=AAPL,MSFT,NVDA&format=csv" -o relative_table.csv
```

With performance metrics:

```bash
curl "http://localhost:8000/api/relative/export?symbols=AAPL,MSFT&perf=return,volatility&perfPeriod=1y&format=csv" -o relative_table.csv
```

## Response Schema

```json
{
  "asOf": "2026-01-29T12:00:00.000000+00:00",
  "requested": {
    "symbols": ["AAPL", "MSFT"],
    "fields": ["sharePrice", "marketCap", "forwardPE"],
    "perf": {
      "period": "3mo",
      "metrics": ["return", "volatility"]
    }
  },
  "rows": [
    {
      "symbol": "AAPL",
      "snapshot": {
        "sharePrice": 185.50,
        "marketCap": 2900000000000,
        "forwardPE": 28.5
      },
      "performance": {
        "return": 0.125,
        "volatility": 0.23
      },
      "error": null
    }
  ]
}
```

## Available Metrics

### Snapshot Fields

| Field | Description | YFinance Key |
|-------|-------------|--------------|
| `sharePrice` | Current stock price | currentPrice / regularMarketPrice |
| `marketCap` | Market capitalization | marketCap |
| `enterpriseValue` | Enterprise value | enterpriseValue |
| `forwardPE` | Forward P/E ratio | forwardPE |
| `priceSales` | Price to sales ratio | priceToSalesTrailing12Months |
| `priceBook` | Price to book ratio | priceToBook |
| `evEbitda` | EV/EBITDA | enterpriseToEbitda |
| `evRevenue` | EV/Revenue | enterpriseToRevenue |
| `profitMargin` | Profit margin (decimal) | profitMargins |
| `roa` | Return on assets (decimal) | returnOnAssets |
| `roe` | Return on equity (decimal) | returnOnEquity |
| `debtEquity` | Debt to equity ratio | debtToEquity |
| `beta` | Beta | beta |

### Performance Metrics

| Metric | Description | Formula |
|--------|-------------|---------|
| `return` | Total return | (last_close / first_close) - 1 |
| `volatility` | Annualized volatility | std(daily_returns) × √252 |
| `maxDrawdown` | Maximum drawdown | min(close / cummax(close) - 1) |

### Performance Periods

`1mo`, `3mo`, `6mo`, `ytd`, `1y`, `2y`, `5y`, `10y`, `max`

## Response Headers

| Header | Description |
|--------|-------------|
| `X-Cache` | `HIT` if all data served from cache, `MISS` otherwise |
| `X-AsOf` | ISO timestamp (CSV export only) |

## Error Handling

- Invalid symbols: Returns row with `error` field populated
- Missing data: Fields set to `null` (keys always present)
- Validation errors: 400 status with descriptive message

## Configuration

Configuration constants are centralized in `app/core/config.py`:

- `MAX_SYMBOLS_PER_REQUEST`: 30
- `CACHE_TTL_SECONDS`: 120
- `MAX_WORKERS`: 10 (ThreadPoolExecutor)
- `FETCH_TIMEOUT_SECONDS`: 30

## License

MIT
