"""Market data from Yahoo Finance (via yfinance), cached in memory.

Every Yahoo call goes through ``_cached``:

1. Cache hit: return it.
2. Otherwise take the lock for that key, so ten requests for AAPL at the
   same moment make one Yahoo call; the other nine wait and then read the cache.
3. A semaphore caps concurrent Yahoo calls, because Yahoo throttles bursts.

Only successes are cached. If Yahoo fails, the error goes back to the caller
and the next request tries again, instead of serving an empty row for minutes.

Three caches, one per kind of data:
- info       quote + fundamentals (price, multiples, cash, debt, shares)  2 min
- history    return / volatility / drawdown per (symbol, period)          2 min
- cashflow   trailing-twelve-month cash flow statement (DCF only)          1 hour
"""

import logging
import math
import threading
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError, as_completed
from datetime import datetime, timezone
from typing import Any, Callable, Optional

import numpy as np
import pandas as pd
import yfinance as yf
from cachetools import TTLCache

from app.core.config import (
    CACHE_TTL_SECONDS,
    FETCH_TIMEOUT_SECONDS,
    MAX_WORKERS,
    SNAPSHOT_FIELDS_ALLOWLIST,
    STATEMENT_CACHE_TTL_SECONDS,
    YFINANCE_MAX_CONCURRENCY,
)

logger = logging.getLogger(__name__)

TRADING_DAYS_PER_YEAR = 252

_info_cache: TTLCache = TTLCache(maxsize=2000, ttl=CACHE_TTL_SECONDS)
_history_cache: TTLCache = TTLCache(maxsize=2000, ttl=CACHE_TTL_SECONDS)
_cashflow_cache: TTLCache = TTLCache(maxsize=2000, ttl=STATEMENT_CACHE_TTL_SECONDS)

_cache_lock = threading.Lock()                       # TTLCache is not thread-safe
_key_locks: defaultdict = defaultdict(threading.Lock)  # one per cache key (bounded by tickers x periods)
_yahoo_slots = threading.Semaphore(YFINANCE_MAX_CONCURRENCY)


def safe_float(value: Any) -> Optional[float]:
    """float(value), or None for missing, NaN or infinite values."""
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(result) or math.isinf(result) else result


def _cache_get(cache: TTLCache, key: Any) -> Any:
    with _cache_lock:
        return cache.get(key)


def _cached(cache: TTLCache, key: Any, fetch: Callable[[], Any]) -> Any:
    value = _cache_get(cache, key)
    if value is not None:
        return value
    with _cache_lock:
        key_lock = _key_locks[(id(cache), key)]
    with key_lock:
        value = _cache_get(cache, key)  # another thread may have fetched it while we waited
        if value is not None:
            return value
        with _yahoo_slots:
            value = fetch()
        with _cache_lock:
            cache[key] = value
        return value


# ---------------------------------------------------------------------------
# Raw data, one Yahoo call each
# ---------------------------------------------------------------------------

def get_info(symbol: str) -> dict:
    """Yahoo's quote + fundamentals payload for one symbol ({} if unknown)."""
    return _cached(_info_cache, symbol, lambda: yf.Ticker(symbol).info or {})


def get_ttm_cashflow(symbol: str) -> pd.Series:
    """Most recent trailing-twelve-month cash flow statement (empty if unavailable)."""
    def fetch() -> pd.Series:
        statement = yf.Ticker(symbol).ttm_cashflow
        if statement is None or statement.empty:
            return pd.Series(dtype=float)
        return statement.iloc[:, 0]  # columns are periods, newest first
    return _cached(_cashflow_cache, symbol, fetch)


def get_performance(symbol: str, period: str) -> dict[str, Optional[float]]:
    """Total return, annualised volatility and max drawdown over a period.

    Uses dividend- and split-adjusted closes (yfinance's default), so return
    is total return and a split does not look like a crash.
    """
    def fetch() -> dict[str, Optional[float]]:
        close = yf.Ticker(symbol).history(period=period, interval="1d")["Close"].dropna()
        if len(close) < 3:
            raise ValueError(f"not enough price history for {period}")
        daily_returns = close.pct_change().dropna()
        return {
            "return": safe_float(close.iloc[-1] / close.iloc[0] - 1),
            "volatility": safe_float(np.std(daily_returns, ddof=1) * np.sqrt(TRADING_DAYS_PER_YEAR)),
            "maxDrawdown": safe_float((close / close.cummax() - 1).min()),
        }
    return _cached(_history_cache, (symbol, period), fetch)


# ---------------------------------------------------------------------------
# Derived views
# ---------------------------------------------------------------------------

def get_snapshot(symbol: str) -> dict[str, Optional[float]]:
    """All snapshot fields for a symbol, from its info payload."""
    info = get_info(symbol)
    snapshot = {}
    for field, yahoo_keys in SNAPSHOT_FIELDS_ALLOWLIST.items():
        values = (safe_float(info.get(key)) for key in yahoo_keys)
        snapshot[field] = next((v for v in values if v is not None), None)
    return snapshot


def _empty_row(symbol, fields, perf_metrics, include_dcf, error: str) -> dict:
    return {
        "symbol": symbol,
        "snapshot": {f: None for f in fields},
        "performance": {m: None for m in perf_metrics} if perf_metrics else None,
        "dcf": {"dcfPrice": None, "dcfUpside": None} if include_dcf else None,
        "missingFields": list(fields),
        "missingPerf": list(perf_metrics) if perf_metrics else None,
        "error": error,
    }


def _fetch_row(
    symbol: str,
    fields: list[str],
    perf_metrics: Optional[list[str]],
    perf_period: Optional[str],
    include_dcf: bool,
) -> dict:
    """One table row. A failing part is reported in `error`; the rest still shows."""
    errors = []

    try:
        snapshot = get_snapshot(symbol)
    except Exception as exc:
        logger.warning("Snapshot failed for %s: %s", symbol, exc)
        errors.append(f"quote unavailable: {exc}")
        snapshot = {}
    row_snapshot = {f: snapshot.get(f) for f in fields}

    performance = None
    if perf_metrics and perf_period:
        try:
            metrics = get_performance(symbol, perf_period)
        except Exception as exc:
            logger.warning("Performance failed for %s %s: %s", symbol, perf_period, exc)
            errors.append(f"performance unavailable: {exc}")
            metrics = {}
        performance = {m: metrics.get(m) for m in perf_metrics}

    dcf = None
    if include_dcf:
        from app.services.dcf import calculate_dcf

        result = calculate_dcf(symbol)
        valuation = result.get("valuation") or {}
        dcf = {"dcfPrice": valuation.get("targetPrice"), "dcfUpside": valuation.get("upsidePct")}
        if result.get("error"):
            errors.append(f"DCF: {result['error']}")

    return {
        "symbol": symbol,
        "snapshot": row_snapshot,
        "performance": performance,
        "dcf": dcf,
        "missingFields": [f for f in fields if row_snapshot[f] is None],
        "missingPerf": [m for m in perf_metrics if performance[m] is None] if performance else None,
        "error": "; ".join(errors) or None,
    }


class YFinanceService:
    """Builds comparison-table rows for many symbols in parallel."""

    def __init__(self):
        self._executor = ThreadPoolExecutor(max_workers=MAX_WORKERS)

    def get_relative(
        self,
        symbols: list[str],
        fields: list[str],
        perf_metrics: Optional[list[str]] = None,
        perf_period: Optional[str] = None,
        include_dcf: bool = False,
    ) -> tuple[list[dict], bool]:
        """Rows in the requested order, plus whether everything came from cache."""
        cache_hit = all(
            _cache_get(_info_cache, s) is not None
            and (not perf_period or _cache_get(_history_cache, (s, perf_period)) is not None)
            for s in symbols
        )

        futures = {
            self._executor.submit(_fetch_row, s, fields, perf_metrics, perf_period, include_dcf): s
            for s in symbols
        }
        rows_by_symbol = {}
        try:
            for future in as_completed(futures, timeout=FETCH_TIMEOUT_SECONDS):
                symbol = futures[future]
                try:
                    rows_by_symbol[symbol] = future.result()
                except Exception as exc:
                    logger.error("Row failed for %s: %s", symbol, exc)
                    rows_by_symbol[symbol] = _empty_row(symbol, fields, perf_metrics, include_dcf, str(exc))
        except FuturesTimeoutError:
            logger.error("Comparison timed out after %ss", FETCH_TIMEOUT_SECONDS)

        for future, symbol in futures.items():
            if symbol not in rows_by_symbol:
                future.cancel()
                rows_by_symbol[symbol] = _empty_row(
                    symbol, fields, perf_metrics, include_dcf,
                    f"Request timed out after {FETCH_TIMEOUT_SECONDS}s",
                )

        return [rows_by_symbol[s] for s in symbols], cache_hit

    def get_as_of_timestamp(self) -> str:
        return datetime.now(timezone.utc).isoformat()


yfinance_service = YFinanceService()
