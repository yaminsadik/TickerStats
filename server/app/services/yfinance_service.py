"""
YFinance service for fetching stock data with caching and concurrency support.
"""

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Optional
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

    def get_snapshot(self, symbol: str) -> dict[str, Optional[float]]:
        """
        Fetch snapshot metrics for a single symbol.
        Returns dict with all snapshot fields, missing values as None.
        """
        # Check cache first
        if symbol in self._snapshot_cache:
            logger.debug(f"Cache hit for snapshot: {symbol}")
            return self._snapshot_cache[symbol]

        logger.info(f"Fetching snapshot for {symbol}")
        result = {field: None for field in SNAPSHOT_FIELDS_ALLOWLIST}

        try:
            ticker = yf.Ticker(symbol)
            info = ticker.info

            if not info:
                logger.warning(f"No info data found for {symbol}")
                self._snapshot_cache[symbol] = result
                return result

            # Special handling for sharePrice with extended fallback
            share_price = None
            # Try currentPrice first
            share_price = safe_float(info.get("currentPrice"))
            # Fallback to regularMarketPrice
            if share_price is None:
                share_price = safe_float(info.get("regularMarketPrice"))
            # Fallback to fast_info.last_price if available
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
                    continue  # Already handled above
                value = None
                for yf_key in yf_keys:
                    val = info.get(yf_key)
                    value = safe_float(val)
                    if value is not None:
                        break
                result[field] = value

            self._snapshot_cache[symbol] = result
            logger.debug(f"Cached snapshot for {symbol}")

        except Exception as e:
            logger.error(f"Error fetching snapshot for {symbol}: {e}")
            # Return result with all None values on error
            self._snapshot_cache[symbol] = result

        return result

    def get_performance(
        self, symbol: str, period: str, metrics: list[str]
    ) -> tuple[dict[str, Optional[float]], Optional[str]]:
        """
        Compute performance metrics for a symbol over a period.
        Returns (dict with requested metrics, error_message or None).
        """
        cache_key = self._get_cache_key(symbol, period)

        # Check cache first
        if cache_key in self._perf_cache:
            cached = self._perf_cache[cache_key]
            logger.debug(f"Cache hit for performance: {cache_key}")
            return {m: cached["data"].get(m) for m in metrics}, cached.get("error")

        logger.info(f"Fetching performance for {symbol} ({period})")
        result = {"return": None, "volatility": None, "maxDrawdown": None}
        error_msg = None

        try:
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period=period, interval="1d")

            if hist.empty or len(hist) < 2:
                error_msg = f"Insufficient price history for {period} period (<2 data points)"
                logger.warning(f"{error_msg} for {symbol}")
                self._perf_cache[cache_key] = {"data": result, "error": error_msg}
                return {m: result.get(m) for m in metrics}, error_msg

            close = hist["Close"].dropna()

            if len(close) < 2:
                error_msg = f"Insufficient close prices for {period} period (<2 data points)"
                logger.warning(f"{error_msg} for {symbol}")
                self._perf_cache[cache_key] = {"data": result, "error": error_msg}
                return {m: result.get(m) for m in metrics}, error_msg

            # Compute return: (last_close / first_close) - 1
            first_close = float(close.iloc[0])
            last_close = float(close.iloc[-1])
            if first_close > 0:
                total_return = (last_close / first_close) - 1
                result["return"] = safe_float(total_return)

            # Compute daily returns
            daily_returns = close.pct_change().dropna()

            if len(daily_returns) > 1:
                # Volatility: std(daily_returns) * sqrt(252)
                volatility = float(np.std(daily_returns, ddof=1) * np.sqrt(252))
                result["volatility"] = safe_float(volatility)

                # Max Drawdown: min(close / cummax(close) - 1)
                cummax = close.cummax()
                drawdown = (close / cummax) - 1
                max_drawdown = float(drawdown.min())
                result["maxDrawdown"] = safe_float(max_drawdown)

            self._perf_cache[cache_key] = {"data": result, "error": None}
            logger.debug(f"Cached performance for {cache_key}")

        except Exception as e:
            error_msg = f"Error computing performance: {str(e)}"
            logger.error(f"Error fetching performance for {symbol}: {e}")
            self._perf_cache[cache_key] = {"data": result, "error": error_msg}

        return {m: result.get(m) for m in metrics}, error_msg

    def get_dcf(self, symbol: str) -> dict[str, Optional[float]]:
        """
        Fetch DCF valuation for a single symbol.
        Returns dict with dcfPrice and dcfUpside.
        """
        # Check cache first
        if symbol in self._dcf_cache:
            logger.debug(f"Cache hit for DCF: {symbol}")
            return self._dcf_cache[symbol]

        logger.info(f"Calculating DCF for {symbol}")
        result = {"dcfPrice": None, "dcfUpside": None}

        try:
            # Import here to avoid circular imports
            from app.services.dcf_service import calculate_simple_dcf
            
            dcf_result = calculate_simple_dcf(symbol)
            
            result["dcfPrice"] = dcf_result.dcf_price
            result["dcfUpside"] = dcf_result.upside
            
            if dcf_result.error:
                logger.warning(f"DCF calculation warning for {symbol}: {dcf_result.error}")

            self._dcf_cache[symbol] = result
            logger.debug(f"Cached DCF for {symbol}")

        except Exception as e:
            logger.error(f"Error calculating DCF for {symbol}: {e}")
            self._dcf_cache[symbol] = result

        return result

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
