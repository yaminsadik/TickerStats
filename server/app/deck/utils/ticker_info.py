"""
Utility to fetch company information from ticker symbol using yfinance.
"""

import logging
from typing import Optional

import yfinance as yf

logger = logging.getLogger(__name__)


def get_company_info(ticker: str) -> dict[str, Optional[str]]:
    """
    Fetch company name and sector from ticker using yfinance.
    
    Args:
        ticker: Stock ticker symbol
        
    Returns:
        Dict with 'company_name' and 'sector' keys (values may be None if not found)
    """
    result = {
        "company_name": None,
        "sector": None,
    }
    
    try:
        logger.info(f"Fetching company info for {ticker}")
        ticker_obj = yf.Ticker(ticker)
        info = ticker_obj.info
        
        if not info:
            logger.warning(f"No info data found for {ticker}")
            return result
        
        # Get company name - try multiple fields
        company_name = (
            info.get("longName") or 
            info.get("shortName") or 
            info.get("name")
        )
        if company_name:
            result["company_name"] = str(company_name).strip()
        
        # Get sector
        sector = info.get("sector") or info.get("industry")
        if sector:
            result["sector"] = str(sector).strip()
        
        logger.info(f"Found: {result['company_name']} in {result['sector']}")
        
    except Exception as e:
        logger.error(f"Error fetching company info for {ticker}: {e}")
    
    return result


def enrich_request_with_ticker_info(
    ticker: str,
    company_name: Optional[str] = None,
    sector: Optional[str] = None,
) -> tuple[str, str]:
    """
    Enrich request with company name and sector from ticker if not provided.
    
    Args:
        ticker: Stock ticker symbol
        company_name: Optional company name (will fetch if None)
        sector: Optional sector (will fetch if None)
        
    Returns:
        Tuple of (company_name, sector)
        
    Raises:
        ValueError: If company info cannot be fetched and not provided
    """
    # If both provided, return as-is
    if company_name and sector:
        return company_name, sector
    
    # Fetch missing info
    info = get_company_info(ticker)
    
    # Use provided values or fetched values
    final_company_name = company_name or info["company_name"]
    final_sector = sector or info["sector"]
    
    # Validate we have the required info
    if not final_company_name:
        raise ValueError(
            f"Could not determine company name for ticker {ticker}. "
            "Please provide company_name in the request."
        )
    
    if not final_sector:
        raise ValueError(
            f"Could not determine sector for ticker {ticker}. "
            "Please provide sector in the request."
        )
    
    return final_company_name, final_sector
