"""
YFinance service for fetching stock data with caching, concurrency limiting,
and in-flight request coalescing.
"""

import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError as FuturesTimeoutError
from datetime import datetime, timezone
from typing import Any, Optional
import math

import numpy as np
import yfinance as yf
from cachetools import TTLCache

from app.core.config import (
    CACHE_TTL_SECONDS,
    MAX_WORKERS,
    SNAPSHOT_FIELDS_ALLOWLIST,
    FETCH_TIMEOUT_SECONDS,
    DCF_METRICS,
    YFINANCE_MAX_CONCURRENCY,
)

logger = logging.getLogger(__name__)


def safe_float(val) -> Optional[float]:
    """Convert value to float safely, returning None for invalid values."""
    if val is None:
        return None
    try:
        f = float(val)
        if math.isnan(f) or math.isinf(f):
            return None
        return f
    except (ValueError, TypeError):
        return None


# ---------------------------------------------------------------------------
# Global concurrency limiter + in-flight coalescing
# ---------------------------------------------------------------------------

# Semaphore limits how many yfinance API calls run simultaneously.
_yf_semaphore = threading.Semaphore(YFINANCE_MAX_CONCURRENCY)

# In-flight coalescing: prevents "cache stampede" when multiple threads
# request the same cache key simultaneously.  Instead of N redundant
# yfinance calls, only 1 runs and the rest await its result.
_inflight_lock = threading.Lock()
_inflight: dict[str, threading.Event] = {}
_inflight_results: dict[str, Any] = {}
_inflight_errors: dict[str, Optional[Exception]] = {}


def _fetch_with_coalescing(
    key: str,
    fetch_fn,
    cache: TTLCache,
    label: str,
) -> Any:
    """
    Fetch data for `key` with:
    1) Cache check (fast path)
    2) In-flight coalescing (if another thread is already fetching the same key)
    3) Semaphore-limited yfinance call
    4) Stale-on-error: if fetch fails and there WAS a cached value, return stale

    Args:
        key: cache key
        fetch_fn: callable() -> result  (the actual yfinance work)
        cache: the TTLCache to read/write
        label: human-readable label for logging (e.g. "snapshot", "perf:1y")
    """
    # 1) Fast path: cache hit
    if key in cache:
        logger.debug("yfinance cache HIT: %s key=%s", label, key)
        return cache[key]

    # 2) Check if another thread is already fetching this key
    with _inflight_lock:
        if key in _inflight:
            event = _inflight[key]
            logger.debug("yfinance coalescing: waiting on in-flight %s key=%s", label, key)
        else:
            # We are the first -- register ourselves
            event = threading.Event()
            _inflight[key] = event
            _inflight_results.pop(key, None)
            _inflight_errors.pop(key, None)
            event = None  # signal that WE should do the fetch

    if event is not None:
        # Another thread is fetching -- wait for it
        completed = event.wait(timeout=FETCH_TIMEOUT_SECONDS)
        if not completed:
            raise TimeoutError(f"In-flight fetch timeout for {label} key={key}")
        if key in _inflight_results:
            return _inflight_results[key]
        # The leader failed; try cache (maybe stale) or raise
        if key in cache:
            return cache[key]
        err = _inflight_errors.get(key)
        if err:
            raise err
        raise TimeoutError(f"In-flight fetch had no result for {label} key={key}")

    # 3) We are the leader -- acquire semaphore and fetch
    start = time.perf_counter()
    semaphore_wait_start = time.perf_counter()
    acquired = _yf_semaphore.acquire(timeout=FETCH_TIMEOUT_SECONDS)
    semaphore_wait_ms = round((time.perf_counter() - semaphore_wait_start) * 1000, 1)

    if semaphore_wait_ms > 500:
        logger.warning(
            "yfinance semaphore wait: %.0fms for %s key=%s",
            semaphore_wait_ms, label, key,
        )

    if not acquired:
        logger.error("yfinance semaphore timeout for %s key=%s", label, key)
        # Clean up inflight and signal waiters
        with _inflight_lock:
            evt = _inflight.pop(key, None)
            _inflight_errors[key] = TimeoutError(f"Semaphore timeout for {label}")
        if evt:
            evt.set()
        raise TimeoutError(f"yfinance concurrency limit reached for {key}")

    try:
        logger.info("yfinance fetch START: %s key=%s", label, key)
        result = fetch_fn()
        duration_ms = round((time.perf_counter() - start) * 1000, 1)
        logger.info(
            "yfinance fetch DONE: %s key=%s duration=%.0fms",
            label, key, duration_ms,
        )

        # Store in cache
        cache[key] = result

        # Signal waiters
        with _inflight_lock:
            _inflight_results[key] = result
            evt = _inflight.pop(key, None)
        if evt:
            evt.set()

        return result

    except Exception as exc:
        duration_ms = round((time.perf_counter() - start) * 1000, 1)
        logger.error(
            "yfinance fetch FAIL: %s key=%s duration=%.0fms error=%s",
            label, key, duration_ms, exc,
        )

        # Stale-on-error: if there was a cached value, return it
        if key in cache:
            logger.warning(
                "yfinance returning stale cache for %s key=%s after error",
                label, key,
            )
            stale = cache[key]
            with _inflight_lock:
                _inflight_results[key] = stale
                evt = _inflight.pop(key, None)
            if evt:
                evt.set()
            return stale

        # No cached value -- propagate the error
        with _inflight_lock:
            _inflight_errors[key] = exc
            evt = _inflight.pop(key, None)
        if evt:
            evt.set()
        raise

    finally:
        _yf_semaphore.release()
        # Deferred cleanup of result/error dicts (avoid memory leak)
        # The waiters have already read by now.
        _inflight_results.pop(key, None)
        _inflight_errors.pop(key, None)


class YFinanceService:
    """Service for fetching stock data from yfinance with caching."""

    def __init__(self):
        # Separate caches for snapshot, performance, and DCF data
        self._snapshot_cache: TTLCache = TTLCache(maxsize=1000, ttl=CACHE_TTL_SECONDS)
        self._perf_cache: TTLCache = TTLCache(maxsize=1000, ttl=CACHE_TTL_SECONDS)
        self._dcf_cache: TTLCache = TTLCache(maxsize=1000, ttl=CACHE_TTL_SECONDS * 5)  # DCF cached 5x longer
        self._executor = ThreadPoolExecutor(max_workers=MAX_WORKERS)

    def _get_cache_key(self, symbol: str, perf_period: Optional[str] = None) -> str:
        """Generate cache key."""
        if perf_period:
            return f"{symbol}:{perf_period}"
        return symbol

    def _is_cache_hit(
        self,
        symbols: list[str],
        perf_metrics: Optional[list[str]],
        perf_period: Optional[str],
    ) -> bool:
        """Check if all requested data is in cache."""
        for symbol in symbols:
            # Check snapshot cache
            if symbol not in self._snapshot_cache:
                return False
            # Check perf cache if performance is requested
            if perf_metrics and perf_period:
                perf_key = self._get_cache_key(symbol, perf_period)
                if perf_key not in self._perf_cache:
                    return False
        return True

    def _raw_fetch_snapshot(self, symbol: str) -> dict[str, Optional[float]]:
        """Raw yfinance snapshot fetch (no cache, no semaphore)."""
        result = {field: None for field in SNAPSHOT_FIELDS_ALLOWLIST}

        try:
            ticker = yf.Ticker(symbol)
            info = ticker.info

            if not info:
                logger.warning(f"No info data found for {symbol}")
                return result

            # Special handling for sharePrice with extended fallback
            share_price = None
            share_price = safe_float(info.get("currentPrice"))
            if share_price is None:
                share_price = safe_float(info.get("regularMarketPrice"))
            if share_price is None:
                try:
                    fast_info = ticker.fast_info
                    if hasattr(fast_info, "last_price"):
                        share_price = safe_float(fast_info.last_price)
                except Exception:
                    pass
            result["sharePrice"] = share_price

            # Map other yfinance fields to our schema
            for field, yf_keys in SNAPSHOT_FIELDS_ALLOWLIST.items():
                if field == "sharePrice":
                    continue
                value = None
                for yf_key in yf_keys:
                    val = info.get(yf_key)
                    value = safe_float(val)
                    if value is not None:
                        break
                result[field] = value

        except Exception as e:
            logger.error(f"Error fetching snapshot for {symbol}: {e}")

        return result

    def get_snapshot(self, symbol: str) -> dict[str, Optional[float]]:
        """
        Fetch snapshot metrics for a single symbol.
        Uses cache -> coalescing -> semaphore-limited yfinance call.
        """
        return _fetch_with_coalescing(
            key=symbol,
            fetch_fn=lambda: self._raw_fetch_snapshot(symbol),
            cache=self._snapshot_cache,
            label="snapshot",
        )

    def _raw_fetch_performance(
        self, symbol: str, period: str,
    ) -> dict:
        """Raw yfinance performance fetch (no cache, no semaphore)."""
        result = {"return": None, "volatility": None, "maxDrawdown": None}
        error_msg = None

        try:
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period=period, interval="1d")

            if hist.empty or len(hist) < 2:
                error_msg = f"Insufficient price history for {period} period (<2 data points)"
                logger.warning(f"{error_msg} for {symbol}")
                return {"data": result, "error": error_msg}

            close = hist["Close"].dropna()

            if len(close) < 2:
                error_msg = f"Insufficient close prices for {period} period (<2 data points)"
                logger.warning(f"{error_msg} for {symbol}")
                return {"data": result, "error": error_msg}

            # Compute return
            first_close = float(close.iloc[0])
            last_close = float(close.iloc[-1])
            if first_close > 0:
                total_return = (last_close / first_close) - 1
                result["return"] = safe_float(total_return)

            # Compute daily returns
            daily_returns = close.pct_change().dropna()

            if len(daily_returns) > 1:
                volatility = float(np.std(daily_returns, ddof=1) * np.sqrt(252))
                result["volatility"] = safe_float(volatility)

                cummax = close.cummax()
                drawdown = (close / cummax) - 1
                max_drawdown = float(drawdown.min())
                result["maxDrawdown"] = safe_float(max_drawdown)

        except Exception as e:
            error_msg = f"Error computing performance: {str(e)}"
            logger.error(f"Error fetching performance for {symbol}: {e}")

        return {"data": result, "error": error_msg}

    def get_performance(
        self, symbol: str, period: str, metrics: list[str]
    ) -> tuple[dict[str, Optional[float]], Optional[str]]:
        """
        Compute performance metrics for a symbol over a period.
        Uses cache -> coalescing -> semaphore-limited yfinance call.
        """
        cache_key = self._get_cache_key(symbol, period)

        cached = _fetch_with_coalescing(
            key=cache_key,
            fetch_fn=lambda: self._raw_fetch_performance(symbol, period),
            cache=self._perf_cache,
            label=f"perf:{period}",
        )

        if not isinstance(cached, dict) or "data" not in cached:
            return {m: None for m in metrics}, "Performance data unavailable"

        return {m: cached["data"].get(m) for m in metrics}, cached.get("error")

    def _raw_fetch_dcf(self, symbol: str) -> dict[str, Optional[float]]:
        """Raw DCF calculation (no cache, no semaphore)."""
        result = {"dcfPrice": None, "dcfUpside": None}

        try:
            from app.services.dcf_service import calculate_simple_dcf

            dcf_result = calculate_simple_dcf(symbol)
            result["dcfPrice"] = dcf_result.dcf_price
            result["dcfUpside"] = dcf_result.upside

            if dcf_result.error:
                logger.warning(f"DCF calculation warning for {symbol}: {dcf_result.error}")

        except Exception as e:
            logger.error(f"Error calculating DCF for {symbol}: {e}")

        return result

    def get_dcf(self, symbol: str) -> dict[str, Optional[float]]:
        """
        Fetch DCF valuation for a single symbol.
        Uses cache -> coalescing -> semaphore-limited yfinance call.
        """
        return _fetch_with_coalescing(
            key=symbol,
            fetch_fn=lambda: self._raw_fetch_dcf(symbol),
            cache=self._dcf_cache,
            label="dcf",
        )

    def _fetch_symbol_data(
        self,
        symbol: str,
        fields: list[str],
        perf_metrics: Optional[list[str]],
        perf_period: Optional[str],
        include_dcf: bool = False,
    ) -> dict:
        """Fetch all data for a single symbol."""
        result = {
            "symbol": symbol,
            "snapshot": {},
            "performance": None,
            "dcf": None,
            "missingFields": [],
            "missingPerf": None,
            "error": None,
        }

        errors = []

        try:
            # Get snapshot data
            full_snapshot = self.get_snapshot(symbol)
            # Filter to requested fields only
            result["snapshot"] = {f: full_snapshot.get(f) for f in fields}

            # Track missing snapshot fields
            result["missingFields"] = [f for f in fields if result["snapshot"].get(f) is None]

            # Get performance data if requested
            if perf_metrics and perf_period:
                perf_data, perf_error = self.get_performance(symbol, perf_period, perf_metrics)
                result["performance"] = perf_data

                # Track missing perf metrics
                result["missingPerf"] = [m for m in perf_metrics if perf_data.get(m) is None]

                if perf_error:
                    errors.append(perf_error)

            # Get DCF data if requested
            if include_dcf:
                dcf_data = self.get_dcf(symbol)
                result["dcf"] = dcf_data

        except Exception as e:
            logger.error(f"Error fetching data for {symbol}: {e}")
            errors.append(str(e))
            # Ensure snapshot has all requested fields as None
            result["snapshot"] = {f: None for f in fields}
            result["missingFields"] = fields.copy()
            if perf_metrics:
                result["performance"] = {m: None for m in perf_metrics}
                result["missingPerf"] = perf_metrics.copy()
            if include_dcf:
                result["dcf"] = {"dcfPrice": None, "dcfUpside": None}

        if errors:
            result["error"] = "; ".join(errors)

        return result

    def get_relative(
        self,
        symbols: list[str],
        fields: list[str],
        perf_metrics: Optional[list[str]] = None,
        perf_period: Optional[str] = None,
        include_dcf: bool = False,
    ) -> tuple[list[dict], bool]:
        """
        Fetch relative table data for multiple symbols concurrently.
        Returns (rows, cache_hit_all).

        Thread safety: individual yfinance calls inside _fetch_symbol_data
        are guarded by the global semaphore and coalescing layer, so even
        though we launch up to MAX_WORKERS threads here, the actual
        concurrent yfinance API calls are limited to YFINANCE_MAX_CONCURRENCY.
        """
        # Check cache status before fetching
        cache_hit = self._is_cache_hit(symbols, perf_metrics, perf_period)

        rows = []
        futures_map = {}

        # Submit all fetch tasks
        for symbol in symbols:
            future = self._executor.submit(
                self._fetch_symbol_data, symbol, fields, perf_metrics, perf_period, include_dcf
            )
            futures_map[future] = symbol

        # Collect results preserving order
        results_by_symbol = {}
        try:
            for future in as_completed(futures_map, timeout=FETCH_TIMEOUT_SECONDS):
                symbol = futures_map[future]
                try:
                    result = future.result()
                    results_by_symbol[symbol] = result
                except Exception as e:
                    logger.error(f"Future error for {symbol}: {e}")
                    results_by_symbol[symbol] = {
                        "symbol": symbol,
                        "snapshot": {f: None for f in fields},
                        "performance": {m: None for m in perf_metrics} if perf_metrics else None,
                        "dcf": {"dcfPrice": None, "dcfUpside": None} if include_dcf else None,
                        "missingFields": fields.copy(),
                        "missingPerf": perf_metrics.copy() if perf_metrics else None,
                        "error": str(e),
                    }
        except FuturesTimeoutError:
            logger.error("Timed out waiting for yfinance worker futures after %ss", FETCH_TIMEOUT_SECONDS)

        # Fill in any symbols that never completed (timeout/cancellation path)
        for future, symbol in futures_map.items():
            if symbol in results_by_symbol:
                continue
            future.cancel()
            results_by_symbol[symbol] = {
                "symbol": symbol,
                "snapshot": {f: None for f in fields},
                "performance": {m: None for m in perf_metrics} if perf_metrics else None,
                "dcf": {"dcfPrice": None, "dcfUpside": None} if include_dcf else None,
                "missingFields": fields.copy(),
                "missingPerf": perf_metrics.copy() if perf_metrics else None,
                "error": f"Request timed out after {FETCH_TIMEOUT_SECONDS}s",
            }

        # Preserve original symbol order
        for symbol in symbols:
            if symbol in results_by_symbol:
                rows.append(results_by_symbol[symbol])

        return rows, cache_hit

    def get_as_of_timestamp(self) -> str:
        """Return current UTC timestamp in ISO format."""
        return datetime.now(timezone.utc).isoformat()


# Singleton instance
yfinance_service = YFinanceService()
