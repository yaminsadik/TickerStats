"""
DCF Data Provider - Fetches normalized inputs from yfinance.

All financial statement inputs come from yfinance (server-side).
Every input is traceable with explicit source attribution.
"""

import logging
import math
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Any, Optional

import yfinance as yf
from cachetools import TTLCache

logger = logging.getLogger(__name__)

# Cache for yfinance DCF data (15 min TTL)
_dcf_data_cache: TTLCache = TTLCache(maxsize=500, ttl=900)


def safe_float(val: Any) -> Optional[float]:
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


@dataclass
class DCFInputs:
    """Normalized inputs for DCF calculation."""
    market_price: Optional[float] = None
    shares_outstanding: Optional[float] = None
    cash: Optional[float] = None
    debt: Optional[float] = None
    fcf_0: Optional[float] = None  # Base FCF (TTM or latest FY)
    
    # Optional market data for transparency
    beta: Optional[float] = None
    currency: str = "USD"
    
    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class DCFSources:
    """Source attribution for each input."""
    market_price: str = "unknown"
    shares_outstanding: str = "unknown"
    cash: str = "unknown"
    debt: str = "unknown"
    fcf_0: str = "unknown"
    beta: str = "unknown"
    
    def to_dict(self) -> dict:
        return asdict(self)


class DCFDataProvider:
    """
    Fetches and normalizes DCF inputs from yfinance.
    All data sourcing is explicit and traceable.
    """
    
    def __init__(self):
        self._cache = _dcf_data_cache
    
    def get_inputs(self, ticker: str) -> tuple[DCFInputs, DCFSources, list[str]]:
        """
        Fetch normalized inputs for DCF calculation.
        
        Returns:
            (inputs, sources, warnings)
        """
        cache_key = f"dcf_inputs:{ticker.upper()}"
        if cache_key in self._cache:
            logger.debug(f"Cache hit for DCF inputs: {ticker}")
            return self._cache[cache_key]
        
        inputs = DCFInputs()
        sources = DCFSources()
        warnings: list[str] = []
        
        try:
            stock = yf.Ticker(ticker)
            info = stock.info or {}
            
            # Currency
            inputs.currency = info.get("currency", "USD")
            
            # 1. Market Price - use history for most recent close
            inputs.market_price = self._get_market_price(stock, info)
            if inputs.market_price:
                sources.market_price = "yfinance:history/info.currentPrice"
            else:
                warnings.append("market_price: not available from yfinance, manual input required")
                sources.market_price = "manual_required"
            
            # 2. Shares Outstanding
            inputs.shares_outstanding = safe_float(info.get("sharesOutstanding"))
            if inputs.shares_outstanding:
                sources.shares_outstanding = "yfinance:info.sharesOutstanding"
            else:
                warnings.append("shares_outstanding: not available from yfinance, manual input required")
                sources.shares_outstanding = "manual_required"
            
            # 3. Cash - prefer "Cash And Cash Equivalents" from balance sheet
            inputs.cash = self._get_cash(stock, info)
            if inputs.cash is not None:
                sources.cash = "yfinance:balance_sheet/info.totalCash"
            else:
                warnings.append("cash: not available from yfinance, manual input required")
                sources.cash = "manual_required"
            
            # 4. Debt - prefer "Total Debt", fallback to sum of long/short term
            inputs.debt = self._get_debt(stock, info)
            if inputs.debt is not None:
                sources.debt = "yfinance:balance_sheet/info.totalDebt"
            else:
                warnings.append("debt: not available from yfinance, manual input required")
                sources.debt = "manual_required"
            
            # 5. FCF - Operating Cash Flow - Capital Expenditures
            inputs.fcf_0 = self._get_fcf(stock, info)
            if inputs.fcf_0 is not None:
                sources.fcf_0 = "yfinance:cashflow(operatingCashFlow - capitalExpenditures)"
            else:
                warnings.append("fcf_0: not available from yfinance, manual input required")
                sources.fcf_0 = "manual_required"
            
            # 6. Beta (optional)
            inputs.beta = safe_float(info.get("beta"))
            if inputs.beta:
                sources.beta = "yfinance:info.beta"
            else:
                sources.beta = "not_available"
            
        except Exception as e:
            logger.error(f"Error fetching DCF inputs for {ticker}: {e}")
            warnings.append(f"Error fetching data: {str(e)[:100]}")
        
        result = (inputs, sources, warnings)
        self._cache[cache_key] = result
        return result
    
    def _get_market_price(self, stock: yf.Ticker, info: dict) -> Optional[float]:
        """Get market price with fallbacks."""
        # Try currentPrice first
        price = safe_float(info.get("currentPrice"))
        if price:
            return price
        
        # Fallback to regularMarketPrice
        price = safe_float(info.get("regularMarketPrice"))
        if price:
            return price
        
        # Fallback to recent history
        try:
            hist = stock.history(period="5d")
            if not hist.empty and "Close" in hist.columns:
                price = safe_float(hist["Close"].iloc[-1])
                if price:
                    return price
        except Exception:
            pass
        
        return None
    
    def _get_cash(self, stock: yf.Ticker, info: dict) -> Optional[float]:
        """Get cash with fallbacks from balance sheet."""
        # Try info.totalCash first
        cash = safe_float(info.get("totalCash"))
        if cash is not None:
            return cash
        
        # Try balance sheet
        try:
            bs = stock.balance_sheet
            if bs is not None and not bs.empty:
                for field_name in [
                    "Cash And Cash Equivalents",
                    "Cash Cash Equivalents And Short Term Investments",
                    "Cash",
                    "Cash Financial",
                ]:
                    if field_name in bs.index:
                        val = safe_float(bs.loc[field_name].iloc[0])
                        if val is not None:
                            return val
        except Exception:
            pass
        
        return None
    
    def _get_debt(self, stock: yf.Ticker, info: dict) -> Optional[float]:
        """Get total debt with fallbacks."""
        # Try info.totalDebt first
        debt = safe_float(info.get("totalDebt"))
        if debt is not None:
            return debt
        
        # Try balance sheet
        try:
            bs = stock.balance_sheet
            if bs is not None and not bs.empty:
                # Try Total Debt first
                if "Total Debt" in bs.index:
                    val = safe_float(bs.loc["Total Debt"].iloc[0])
                    if val is not None:
                        return val
                
                # Fallback: Long Term Debt + Current portion
                long_term = 0.0
                short_term = 0.0
                
                for field_name in ["Long Term Debt", "Long Term Debt And Capital Lease Obligation"]:
                    if field_name in bs.index:
                        val = safe_float(bs.loc[field_name].iloc[0])
                        if val is not None:
                            long_term = val
                            break
                
                for field_name in ["Current Long Term Debt", "Current Debt", "Short Long Term Debt"]:
                    if field_name in bs.index:
                        val = safe_float(bs.loc[field_name].iloc[0])
                        if val is not None:
                            short_term = val
                            break
                
                if long_term > 0 or short_term > 0:
                    return long_term + short_term
        except Exception:
            pass
        
        return None
    
    def _get_fcf(self, stock: yf.Ticker, info: dict) -> Optional[float]:
        """
        Get Free Cash Flow = Operating Cash Flow - Capital Expenditures.
        
        Note: CAPEX is typically reported as negative in yfinance.
        FCF = OCF - CapEx (where CapEx is negative, so subtracting negative adds)
        """
        # Try info.freeCashflow first
        fcf = safe_float(info.get("freeCashflow"))
        if fcf is not None:
            return fcf
        
        # Calculate from cash flow statement
        try:
            cf = stock.cashflow
            if cf is not None and not cf.empty:
                ocf: Optional[float] = None
                capex: Optional[float] = None
                
                # Get Operating Cash Flow
                for field_name in [
                    "Operating Cash Flow",
                    "Cash Flow From Continuing Operating Activities",
                    "Total Cash From Operating Activities",
                ]:
                    if field_name in cf.index:
                        ocf = safe_float(cf.loc[field_name].iloc[0])
                        if ocf is not None:
                            break
                
                # Get Capital Expenditures (typically negative)
                for field_name in [
                    "Capital Expenditure",
                    "Capital Expenditures",
                    "Purchase Of Property Plant Equipment",
                ]:
                    if field_name in cf.index:
                        capex = safe_float(cf.loc[field_name].iloc[0])
                        if capex is not None:
                            break
                
                if ocf is not None and capex is not None:
                    # CapEx is typically negative, so OCF - CapEx = OCF + |CapEx|
                    return ocf - capex
                elif ocf is not None:
                    # If no CapEx found, just use OCF as estimate (with warning)
                    logger.warning(f"CapEx not found, using OCF as FCF estimate")
                    return ocf
        except Exception as e:
            logger.debug(f"Error calculating FCF from cashflow: {e}")
        
        return None


# Module-level singleton
_provider: Optional[DCFDataProvider] = None


def get_dcf_data_provider() -> DCFDataProvider:
    """Get the singleton DCF data provider."""
    global _provider
    if _provider is None:
        _provider = DCFDataProvider()
    return _provider
