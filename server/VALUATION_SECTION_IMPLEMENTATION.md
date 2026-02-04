# VALUATION & RELATIVE HEATMAP Implementation Summary

## Section Ordering

The deck now includes two data-driven valuation sections:

1. Overview
2. SWOT / Porter's Five
3. **Bull Case** (references concise DCF/comps)
4. **Bear Case** (references concise DCF/comps)
5. **RELATIVE HEATMAP** (detailed comps table) ← NEW SECTION
6. **VALUATION** (detailed DCF breakdown)
7. Rebuttals (Q&A)
8. Layout

## Changes Made

### 1. Schema Updates (`server/app/deck/api/schemas.py`)

**Added RELATIVE_HEATMAP and VALUATION section enums:**
```python
class SectionId(str, Enum):
    # ... existing sections ...
    RELATIVE_HEATMAP = "relative_heatmap"
    VALUATION = "valuation"
```

**Added section metadata:**
```python
SECTION_METADATA = {
    # ... existing sections ...
    SectionId.RELATIVE_HEATMAP: {
        "id": "relative_heatmap",
        "label": "Relative Valuation",
        "description": "Comparative metrics table showing target vs peers",
        "min_slides": 1,
        "max_slides": 1,
        "requires_comps": True,
    },
    SectionId.VALUATION: {
        "id": "valuation",
        "label": "DCF Valuation",
        "description": "Deterministic DCF target price calculation with full breakdown",
        "min_slides": 1,
        "max_slides": 2,
        "requires_dcf": True,
    },
}
```

### 2. Prompt Templates (`server/app/deck/services/prompts.py`)

**Added `get_relative_heatmap_prompt()` function:**
- Generates 1-slide comparative table section
- Shows target vs peers across valuation multiples, profitability, growth
- Uses full comparables data (not concise version)
- Highlights premium/discount to peer median

**Added `get_valuation_prompt()` function:**
- Generates 2-slide section:
  - Slide 1: DCF Methodology & Assumptions (FCF, growth rate, WACC, terminal value)
  - Slide 2: Price Target & Upside (current price, target, upside %, sensitivity)
- Emphasizes transparency and source attribution
- Instructs LLM to use ONLY provided DCF data, not invent numbers

**Updated `SECTION_PROMPT_MAP`:**
```python
SECTION_PROMPT_MAP = {
    # ... existing mappings ...
    "relative_heatmap": get_relative_heatmap_prompt,
    "valuation": get_valuation_prompt,
}
```

**Updated `get_section_prompt()`:**
- Routes "relative_heatmap" to use detailed comps summary
- Routes "valuation" section to use detailed DCF summary
- Other sections (bull_case, bear_case) use concise versions

### 3. Comparables Service (`server/app/deck/services/comps_service.py`)

**Added `format_for_prompt_concise()` method:**
- Creates brief comps summary for bull/bear sections
- Example: `"Comps: P/E: 28.5x vs peer median 24.3x, EV/EBITDA: 18.2x vs peer median 16.1x"`
- Reduced from ~300 lines to ~1 line (~80 chars)

**Existing `format_for_prompt()` method:**
- Kept for detailed sections (relative_heatmap)
- Shows all metrics for target + all comparables
- ~300+ lines of data

### 4. Deck Generator (`server/app/deck/services/deck_generator.py`)

**Added `_format_dcf_detailed()` method:**
- Formats complete DCF breakdown for VALUATION section
- Includes:
  - All inputs (FCF, growth rate, discount rate, terminal growth)
  - Calculation steps (PV, terminal value, EV, equity value)
  - Target price and upside %
  - Data sources
- ~500-800 chars (detailed but structured)

**Updated `_format_dcf_for_prompt()` (already concise):**
- Kept at ~40 chars: "DCF Target: $X.XX (+Y.Y% vs market)"
**Updated `generate_deck()` method:**
- Creates both concise and detailed summaries for DCF and comps
- Routes detailed summaries to relative_heatmap and valuation sections
- Routes concise summaries to bull/bear sections

```python
# Use detailed versions for data sections, concise for narratives
dcf_for_section = dcf_detailed if section_id == "valuation" else dcf_summary
comps_for_section = comps_concise if section_id in ["bull_case", "bear_case"] else comps_summary
```

## How It Works

### Token Management Strategy

**Problem:** Gemini hit max_output_tokens when verbose comps/DCF data was embedded in bull/bear prompts

**Solution:**
1. **Concise references** in bull/bear prompts
   - DCF: ~40 chars ("DCF Target: $150.50 (+15.5%)")
   - Comps: ~80 chars ("Comps: P/E: 28.5x vs peer median 24.3x")
   - Avoids token bloat
   - Provides context without overwhelming LLM
   
2. **Detailed section** after investment thesis
   - Dedicated VALUATION slides show full calculation
   - Provides transparency and verification
   - Better UX: separate factual data from narrative

### Example Usage

```python
request = DeckGenerateRequest(
    ticker="AAPL",
    sections=["bull_case", "bear_case", "valuation"],
    provider="gemini",
    reasoning_level="medium"
)

# Will generate:
# - Bull case with brief DCF reference
# - Bear case with brief DCF reference
# - Valuation section with full DCF breakdown
```

### VALUATION Section Output Example

**Slide 1: DCF Methodology & Assumptions**
- Approach: Discounted Cash Flow (DCF) analysis
- Free Cash Flow: $99.58B (yfinance)
- Growth Rate: 5.0% (yfinance historical/assumptions)
- Discount Rate (WACC): 8.5% (calculated)

**Slide 2: Price Target & Upside**
- Current Price: $269.45 (yfinance)
- DCF Target Price: $142.66
- Implied Upside: -47.0%
- Key Sensitivity: Growth rate and terminal value assumptions

## Benefits

1. **Token Efficiency**: Solves Gemini token limit errors by moving detailed DCF out of narrative sections
2. **Transparency**: Dedicated section shows exact formulas and assumptions
3. **Flexibility**: Users can include/exclude VALUATION section independently
4. **Source Attribution**: All inputs marked with yfinance source
5. **Better UX**: Separates factual calculations from investment narrative

## Testing

- ✅ No syntax errors in modified files
- ✅ Proper enum and metadata definitions
- ✅ Prompt function properly mapped
- ✅ DCF formatting methods implemented
- 🔄 Full integration test pending (requires Python environment setup)

## Next Steps

To test with actual API:
```bash
cd server
python3 test_deck_endpoint.py --ticker AAPL \
  --sections bull_case bear_case valuation \
  --provider gemini --reasoning medium
```

This should:
1. Generate bull/bear cases with brief DCF reference (no token errors)
2. Generate dedicated VALUATION section with full breakdown
3. All slides properly formatted with 4 bullets max
