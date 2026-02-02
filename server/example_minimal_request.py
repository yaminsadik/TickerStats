"""
Example: Minimal deck generation request - only ticker needed!
"""

import os
import sys
from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, os.path.dirname(__file__))

def minimal_example():
    """Show minimal request example."""
    from app.deck.api.schemas import DeckGenerateRequest
    from app.deck.services.deck_generator import DeckGenerator, DeckGeneratorConfig
    from app.deck.utils.ticker_info import enrich_request_with_ticker_info
    
    print("=" * 70)
    print("MINIMAL DECK GENERATION REQUEST - ONLY TICKER NEEDED!")
    print("=" * 70)
    
    # Create minimal request - only ticker + fund constraints
    minimal_request = DeckGenerateRequest(
        ticker="TSLA",  # ← Only need ticker!
        # company_name and sector will be auto-fetched
        fund_constraints={
            "time_horizon": "18 months",
            "risk_profile": "aggressive",
        },
        provider="gemini",
        sections=["overview", "swot"],
    )
    
    print("\n✅ Request created with just:")
    print(f"   • ticker: {minimal_request.ticker}")
    print(f"   • fund_constraints")
    print(f"   • provider: {minimal_request.provider.value}")
    print(f"   • sections: {minimal_request.sections}")
    
    print(f"\n🔍 Before auto-fetch:")
    print(f"   • company_name: {minimal_request.company_name}")
    print(f"   • sector: {minimal_request.sector}")
    
    # Auto-fetch company info
    print(f"\n⏳ Auto-fetching company info from yfinance...")
    company_name, sector = enrich_request_with_ticker_info(
        ticker=minimal_request.ticker,
        company_name=minimal_request.company_name,
        sector=minimal_request.sector,
    )
    minimal_request.company_name = company_name
    minimal_request.sector = sector
    
    print(f"\n✨ After auto-fetch:")
    print(f"   • company_name: {minimal_request.company_name}")
    print(f"   • sector: {minimal_request.sector}")
    
    print("\n" + "=" * 70)
    print("✅ SUCCESS! You can now generate deck with just the ticker!")
    print("=" * 70)
    
    # Show example API request
    print("\n📝 Example API Request (minimal):")
    print("""
    POST /api/v1/deck/generate
    {
      "ticker": "TSLA",
      "fund_constraints": {
        "time_horizon": "18 months",
        "risk_profile": "aggressive"
      },
      "provider": "gemini",
      "sections": ["overview", "swot"]
    }
    
    ↓ Auto-fetches company_name and sector from yfinance!
    """)
    
    return True

if __name__ == "__main__":
    try:
        success = minimal_example()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
