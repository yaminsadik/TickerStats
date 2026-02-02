"""
Comparables service wrapper for deck generation.
Wraps the existing yfinance service to provide comps table data.
"""

from typing import Any, Optional

from app.deck.utils.cache import get_cache
from app.deck.utils.logging import get_logger, log_operation
from app.services.yfinance_service import yfinance_service

logger = get_logger(__name__)


# Default comparable sectors with typical peer companies
# These are fallbacks when no specific comps are provided
DEFAULT_SECTOR_COMPS = {
    "Technology": ["AAPL", "MSFT", "GOOGL", "META", "NVDA"],
    "IT": ["ACN", "IBM", "ORCL", "CRM", "SAP"],
    "Financials": ["JPM", "BAC", "GS", "MS", "C"],
    "Healthcare": ["JNJ", "UNH", "PFE", "MRK", "ABBV"],
    "Consumer Discretionary": ["AMZN", "TSLA", "HD", "NKE", "MCD"],
    "Consumer Staples": ["PG", "KO", "PEP", "WMT", "COST"],
    "Energy": ["XOM", "CVX", "COP", "SLB", "EOG"],
    "Industrials": ["HON", "UPS", "CAT", "BA", "GE"],
    "Materials": ["LIN", "APD", "SHW", "FCX", "NEM"],
    "Real Estate": ["AMT", "PLD", "CCI", "EQIX", "SPG"],
    "Utilities": ["NEE", "DUK", "SO", "D", "AEP"],
    "Communication Services": ["GOOGL", "META", "DIS", "NFLX", "VZ"],
}

# Key metrics for comps table
COMPS_SNAPSHOT_FIELDS = [
    "sharePrice",
    "marketCap",
    "enterpriseValue",
    "forwardPE",
    "priceSales",
    "priceBook",
    "evEbitda",
    "evRevenue",
    "profitMargin",
    "roe",
]

COMPS_PERF_METRICS = ["return", "volatility"]
COMPS_PERF_PERIOD = "1y"


class CompsService:
    """
    Service for fetching comparable company data for pitch decks.
    Wraps the existing yfinance service and adds deck-specific formatting.
    """
    
    def __init__(self):
        self._cache = get_cache()
    
    def _get_sector_comps(self, sector: str, exclude_ticker: str) -> list[str]:
        """
        Get default comparable tickers for a sector.
        
        Args:
            sector: Industry sector name
            exclude_ticker: Ticker to exclude (the target company)
            
        Returns:
            List of comparable ticker symbols
        """
        # Try exact match first
        comps = DEFAULT_SECTOR_COMPS.get(sector, [])
        
        # Try partial match if no exact match
        if not comps:
            sector_lower = sector.lower()
            for key, tickers in DEFAULT_SECTOR_COMPS.items():
                if key.lower() in sector_lower or sector_lower in key.lower():
                    comps = tickers
                    break
        
        # Fall back to tech sector as default
        if not comps:
            comps = DEFAULT_SECTOR_COMPS.get("Technology", [])
        
        # Exclude target ticker
        return [t for t in comps if t.upper() != exclude_ticker.upper()][:5]
    
    @log_operation("fetch_comps_table")
    def get_comps_table(
        self,
        ticker: str,
        sector: str,
        comp_tickers: Optional[list[str]] = None,
        include_performance: bool = True,
    ) -> dict[str, Any]:
        """
        Fetch comparables table data for a ticker.
        
        Args:
            ticker: Target company ticker
            sector: Industry sector for default comps
            comp_tickers: Optional explicit list of comparable tickers
            include_performance: Whether to include 1Y performance metrics
            
        Returns:
            Dict with comps table data formatted for deck generation
        """
        # Determine comparison tickers
        if comp_tickers:
            symbols = [ticker.upper()] + [t.upper() for t in comp_tickers if t.upper() != ticker.upper()]
        else:
            sector_comps = self._get_sector_comps(sector, ticker)
            symbols = [ticker.upper()] + sector_comps
        
        # Limit to 6 companies total (target + 5 comps)
        symbols = symbols[:6]
        
        # Check cache
        cached = self._cache.get_comps(ticker, symbols)
        if cached:
            logger.info(f"Returning cached comps for {ticker}")
            return cached
        
        logger.info(f"Fetching comps table for {ticker}", extra={
            "symbols": symbols,
            "include_performance": include_performance,
        })
        
        # Fetch data using existing service
        perf_metrics = COMPS_PERF_METRICS if include_performance else None
        perf_period = COMPS_PERF_PERIOD if include_performance else None
        
        rows, _ = yfinance_service.get_relative(
            symbols=symbols,
            fields=COMPS_SNAPSHOT_FIELDS,
            perf_metrics=perf_metrics,
            perf_period=perf_period,
        )
        
        # Format for deck generation
        result = self._format_comps_result(ticker, rows, include_performance)
        
        # Cache result
        self._cache.set_comps(ticker, symbols, result)
        
        return result
    
    def _format_comps_result(
        self,
        target_ticker: str,
        rows: list[dict],
        include_performance: bool,
    ) -> dict[str, Any]:
        """
        Format raw yfinance data into deck-friendly structure.
        
        Args:
            target_ticker: The target company ticker
            rows: Raw rows from yfinance service
            include_performance: Whether performance data is included
            
        Returns:
            Formatted comps table dict
        """
        target_row = None
        comp_rows = []
        
        for row in rows:
            if row["symbol"].upper() == target_ticker.upper():
                target_row = row
            else:
                comp_rows.append(row)
        
        # Calculate summary statistics
        summary = self._calculate_summary(comp_rows)
        
        result = {
            "target": self._format_row(target_row) if target_row else None,
            "comparables": [self._format_row(r) for r in comp_rows],
            "summary": summary,
            "metrics_included": {
                "snapshot": COMPS_SNAPSHOT_FIELDS,
                "performance": COMPS_PERF_METRICS if include_performance else [],
            },
            "data_quality": {
                "target_complete": target_row is not None and not target_row.get("missingFields"),
                "comps_count": len(comp_rows),
                "comps_with_errors": sum(1 for r in comp_rows if r.get("error")),
            },
        }
        
        return result
    
    def _format_row(self, row: dict) -> dict:
        """Format a single row for the comps table."""
        return {
            "ticker": row["symbol"],
            "snapshot": row.get("snapshot", {}),
            "performance": row.get("performance"),
            "missing_fields": row.get("missingFields", []),
            "has_error": bool(row.get("error")),
        }
    
    def _calculate_summary(self, comp_rows: list[dict]) -> dict:
        """
        Calculate summary statistics for comparables.
        
        Args:
            comp_rows: List of comparable company rows
            
        Returns:
            Dict with median, mean, min, max for each metric
        """
        summary = {
            "median": {},
            "mean": {},
            "min": {},
            "max": {},
        }
        
        if not comp_rows:
            return summary
        
        # Collect values for each metric
        for field in COMPS_SNAPSHOT_FIELDS:
            values = [
                r["snapshot"].get(field)
                for r in comp_rows
                if r.get("snapshot", {}).get(field) is not None
            ]
            
            if values:
                sorted_values = sorted(values)
                n = len(values)
                
                summary["median"][field] = (
                    sorted_values[n // 2] if n % 2 == 1
                    else (sorted_values[n // 2 - 1] + sorted_values[n // 2]) / 2
                )
                summary["mean"][field] = sum(values) / n
                summary["min"][field] = min(values)
                summary["max"][field] = max(values)
        
        # Performance metrics
        for metric in COMPS_PERF_METRICS:
            values = [
                r.get("performance", {}).get(metric)
                for r in comp_rows
                if r.get("performance", {}).get(metric) is not None
            ]
            
            if values:
                sorted_values = sorted(values)
                n = len(values)
                
                summary["median"][metric] = (
                    sorted_values[n // 2] if n % 2 == 1
                    else (sorted_values[n // 2 - 1] + sorted_values[n // 2]) / 2
                )
                summary["mean"][metric] = sum(values) / n
                summary["min"][metric] = min(values)
                summary["max"][metric] = max(values)
        
        return summary
    
    def format_for_prompt(self, comps_data: dict) -> str:
        """
        Format comps data for inclusion in LLM prompts.
        
        Args:
            comps_data: Comps table data from get_comps_table
            
        Returns:
            Formatted string for prompt inclusion
        """
        lines = ["COMPARABLES TABLE DATA (for context only - do not fabricate additional numbers):"]
        lines.append("")
        
        target = comps_data.get("target")
        if target:
            lines.append(f"TARGET COMPANY: {target['ticker']}")
            snapshot = target.get("snapshot", {})
            for key, value in snapshot.items():
                if value is not None:
                    lines.append(f"  {key}: {self._format_value(key, value)}")
            lines.append("")
        
        lines.append("COMPARABLE COMPANIES:")
        for comp in comps_data.get("comparables", []):
            lines.append(f"\n  {comp['ticker']}:")
            snapshot = comp.get("snapshot", {})
            for key, value in snapshot.items():
                if value is not None:
                    lines.append(f"    {key}: {self._format_value(key, value)}")
        
        summary = comps_data.get("summary", {})
        if summary.get("median"):
            lines.append("\nCOMP GROUP MEDIANS:")
            for key, value in summary["median"].items():
                if value is not None:
                    lines.append(f"  {key}: {self._format_value(key, value)}")
        
        lines.append("\nNOTE: Use this data for qualitative context only. Do not fabricate numbers.")
        lines.append("If you need to cite a specific metric, mark it with (source needed).")
        
        return "\n".join(lines)
    
    def _format_value(self, key: str, value: float) -> str:
        """Format a metric value for display."""
        if value is None:
            return "N/A"
        
        # Percentage metrics
        if key in ["profitMargin", "roe", "roa", "return", "volatility", "maxDrawdown"]:
            return f"{value * 100:.1f}%"
        
        # Large numbers
        if key in ["marketCap", "enterpriseValue"]:
            if value >= 1e12:
                return f"${value / 1e12:.1f}T"
            elif value >= 1e9:
                return f"${value / 1e9:.1f}B"
            elif value >= 1e6:
                return f"${value / 1e6:.1f}M"
            return f"${value:,.0f}"
        
        # Price
        if key == "sharePrice":
            return f"${value:.2f}"
        
        # Ratios
        if key in ["forwardPE", "priceSales", "priceBook", "evEbitda", "evRevenue", "beta", "debtEquity"]:
            return f"{value:.2f}x" if value != 0 else "0"
        
        return f"{value:.2f}"


# Singleton instance
comps_service = CompsService()
