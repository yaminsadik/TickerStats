"""
Section-specific prompts for deck generation.
Contains system prompts and section prompt templates.
"""

from typing import Any, Optional


# =============================================================================
# SHARED SYSTEM PROMPT
# =============================================================================

SYSTEM_PROMPT = """You are an expert investment analyst assistant specializing in creating professional pitch deck content for student investment funds. Your role is to generate clear, concise, and fund-ready slide content.

CRITICAL RULES:
1. OUTPUT FORMAT: Respond ONLY with valid JSON. No markdown, no explanations, no code blocks.
2. BULLET LIMIT: Maximum 4 bullets per slide. Each bullet must be concise (under 100 characters when possible).
3. NO FABRICATED NUMBERS: Do not invent financial metrics, percentages, or statistics. If a number is needed and not provided, write "(source needed)" and set the appropriate flag.
4. PROFESSIONAL TONE: Write for a sophisticated investment committee audience.
5. ACTIONABLE CONTENT: Every bullet should convey a meaningful insight, not filler.
6. SPEAKER NOTES: Provide presenter talking points that expand on bullets without reading them verbatim.

STYLE GUIDELINES:
- Use active voice and strong verbs
- Lead with the most important point
- Avoid jargon unless industry-standard
- Be specific rather than generic
- Include "why it matters" context where appropriate"""


# =============================================================================
# SECTION-SPECIFIC PROMPTS
# =============================================================================

def get_overview_prompt(
    ticker: str,
    company_name: str,
    sector: str,
    fund_constraints: dict,
    comps_summary: Optional[str] = None,
) -> str:
    """Generate prompt for Company Overview section."""
    
    comps_section = f"\n\n{comps_summary}" if comps_summary else ""
    
    return f"""Generate the Company Overview section for {company_name} ({ticker}) in the {sector} sector.

CONTEXT:
- Fund Style: {fund_constraints.get('style', 'Student investment fund pitch')}
- Time Horizon: {fund_constraints.get('time_horizon', '12-24 months')}
- Risk Profile: {fund_constraints.get('risk_profile', 'Moderate')}
{f"- Portfolio Context: {fund_constraints.get('portfolio_context')}" if fund_constraints.get('portfolio_context') else ""}
{comps_section}

REQUIRED CONTENT:
1. What the business does (core value proposition)
2. Business segments/revenue streams
3. "Why Now" thesis - what makes this timely
4. Key catalysts for the investment thesis

Generate 2-3 slides covering these topics. Each slide must have:
- A clear, descriptive title
- 3-4 concise bullets
- Speaker notes for the presenter
- Layout hints

If you include any quantitative claims (market size, growth rates, etc.), mark them with "(source needed)" and set flags.needs_sources = true.

Respond with a JSON object matching this structure:
{{
  "section_id": "overview",
  "slides": [
    {{
      "slide_id": "overview_1",
      "title": "...",
      "bullets": [{{"text": "...", "source_needed": false}}],
      "speaker_notes": "...",
      "layout_hints": {{"style": "bullets", "max_bullets": 4}},
      "flags": {{"needs_sources": false, "contains_numbers": false, "is_draft": false}}
    }}
  ]
}}"""


def get_history_prompt(
    ticker: str,
    company_name: str,
    sector: str,
    fund_constraints: dict,
) -> str:
    """Generate prompt for History Timeline section."""
    
    return f"""Generate the History Timeline section for {company_name} ({ticker}).

CRITICAL: This section is a DRAFT that requires verification. All dates, events, and facts MUST be reviewed by the team before presentation.

CONTEXT:
- Fund Style: {fund_constraints.get('style', 'Student investment fund pitch')}

REQUIRED CONTENT:
- Company founding and early history
- IPO date (if applicable)
- Major acquisitions or divestitures
- Key leadership changes
- Strategic pivots or transformations
- Recent significant events (last 2-3 years)

Generate 1-2 timeline slides. Each bullet should represent a key milestone.

IMPORTANT:
- Set needs_verification: true for the section
- Include verification_notes listing specific items to verify
- Mark any uncertain dates or claims
- Prefer general timeframes ("early 2010s") over specific dates you're uncertain about

Respond with JSON:
{{
  "section_id": "history",
  "needs_verification": true,
  "verification_notes": ["Verify IPO date", "Confirm acquisition timing", "..."],
  "slides": [
    {{
      "slide_id": "history_1",
      "title": "Company Timeline",
      "bullets": [{{"text": "YYYY: Key event (verify)", "source_needed": true}}],
      "speaker_notes": "...",
      "layout_hints": {{"style": "timeline", "max_bullets": 4, "suggested_visual": "timeline"}},
      "flags": {{"needs_sources": true, "contains_numbers": true, "is_draft": true}}
    }}
  ]
}}"""


def get_swot_prompt(
    ticker: str,
    company_name: str,
    sector: str,
    fund_constraints: dict,
    comps_summary: Optional[str] = None,
) -> str:
    """Generate prompt for SWOT Analysis section."""
    
    comps_section = f"\n\n{comps_summary}" if comps_summary else ""
    
    return f"""Generate a SWOT Analysis for {company_name} ({ticker}) in the {sector} sector.

CONTEXT:
- Fund Style: {fund_constraints.get('style', 'Student investment fund pitch')}
- Time Horizon: {fund_constraints.get('time_horizon', '12-24 months')}
- Risk Profile: {fund_constraints.get('risk_profile', 'Moderate')}
{comps_section}

REQUIRED CONTENT:
Generate 2-3 slides covering all four SWOT categories:

SLIDE 1 - Strengths & Weaknesses (Internal):
- STRENGTHS: Competitive advantages, unique capabilities, strong market position
- WEAKNESSES: Operational challenges, competitive gaps, structural issues

SLIDE 2 - Opportunities & Threats (External):
- OPPORTUNITIES: Market trends, expansion potential, favorable conditions
- THREATS: Competitive pressure, regulatory risks, macro headwinds

Each point should include brief justification (why this matters for the thesis).

Respond with JSON:
{{
  "section_id": "swot",
  "slides": [
    {{
      "slide_id": "swot_1",
      "title": "Strengths & Weaknesses",
      "bullets": [
        {{"text": "S: [Strength with brief justification]", "source_needed": false}},
        {{"text": "S: [Another strength]", "source_needed": false}},
        {{"text": "W: [Weakness with brief justification]", "source_needed": false}},
        {{"text": "W: [Another weakness]", "source_needed": false}}
      ],
      "speaker_notes": "...",
      "layout_hints": {{"style": "two_column", "max_bullets": 4}},
      "flags": {{"needs_sources": false, "contains_numbers": false, "is_draft": false}}
    }},
    {{
      "slide_id": "swot_2",
      "title": "Opportunities & Threats",
      "bullets": [
        {{"text": "O: [Opportunity]", "source_needed": false}},
        {{"text": "O: [Another opportunity]", "source_needed": false}},
        {{"text": "T: [Threat]", "source_needed": false}},
        {{"text": "T: [Another threat]", "source_needed": false}}
      ],
      "speaker_notes": "...",
      "layout_hints": {{"style": "two_column", "max_bullets": 4}},
      "flags": {{"needs_sources": false, "contains_numbers": false, "is_draft": false}}
    }}
  ]
}}"""


def get_porters_five_prompt(
    ticker: str,
    company_name: str,
    sector: str,
    fund_constraints: dict,
) -> str:
    """Generate prompt for Porter's Five Forces section."""
    
    return f"""Generate a Porter's Five Forces analysis for {company_name} ({ticker}) in the {sector} sector.

CONTEXT:
- Fund Style: {fund_constraints.get('style', 'Student investment fund pitch')}
- Industry: {sector}

REQUIRED CONTENT:
Analyze all five forces with a rating (Low/Medium/High) and justification:

1. THREAT OF NEW ENTRANTS
   - Barriers to entry, capital requirements, regulatory hurdles

2. BARGAINING POWER OF SUPPLIERS
   - Supplier concentration, switching costs, input criticality

3. BARGAINING POWER OF BUYERS
   - Customer concentration, price sensitivity, switching costs

4. THREAT OF SUBSTITUTES
   - Alternative solutions, switching costs, performance comparison

5. COMPETITIVE RIVALRY
   - Number of competitors, industry growth, differentiation

Generate 1-2 slides presenting this analysis. Use a consistent format for each force.

Respond with JSON:
{{
  "section_id": "porters_five",
  "slides": [
    {{
      "slide_id": "porters_1",
      "title": "Porter's Five Forces Analysis",
      "bullets": [
        {{"text": "New Entrants: [Rating] - [Brief justification]", "source_needed": false}},
        {{"text": "Supplier Power: [Rating] - [Brief justification]", "source_needed": false}},
        {{"text": "Buyer Power: [Rating] - [Brief justification]", "source_needed": false}},
        {{"text": "Substitutes: [Rating] - [Brief justification]", "source_needed": false}}
      ],
      "speaker_notes": "...",
      "layout_hints": {{"style": "bullets", "max_bullets": 4, "suggested_visual": "five_forces_diagram"}},
      "flags": {{"needs_sources": false, "contains_numbers": false, "is_draft": false}}
    }},
    {{
      "slide_id": "porters_2",
      "title": "Competitive Rivalry & Implications",
      "bullets": [
        {{"text": "Rivalry: [Rating] - [Key competitive dynamics]", "source_needed": false}},
        {{"text": "[Implication for investment thesis]", "source_needed": false}},
        {{"text": "[Key takeaway from analysis]", "source_needed": false}}
      ],
      "speaker_notes": "...",
      "layout_hints": {{"style": "bullets", "max_bullets": 4}},
      "flags": {{"needs_sources": false, "contains_numbers": false, "is_draft": false}}
    }}
  ]
}}"""


def get_rebuttals_prompt(
    ticker: str,
    company_name: str,
    sector: str,
    fund_constraints: dict,
) -> str:
    """Generate prompt for Rebuttals/Q&A section."""
    
    return f"""Generate a Rebuttals / Q&A Preparation section for {company_name} ({ticker}).

CONTEXT:
- Fund Style: {fund_constraints.get('style', 'Student investment fund pitch')}
- Time Horizon: {fund_constraints.get('time_horizon', '12-24 months')}
- Risk Profile: {fund_constraints.get('risk_profile', 'Moderate')}

REQUIRED CONTENT:
Anticipate 4-6 tough questions that an investment committee might ask and prepare responses:

Common objection categories:
- Valuation concerns
- Competitive threats
- Macro/sector risks
- Management/execution risks
- Timing concerns

Generate 1-2 slides in Q&A format. Each bullet should be:
"Q: [Objection/Question] → A: [Concise response]"

The responses should acknowledge the concern and provide a measured, evidence-based counter.

Respond with JSON:
{{
  "section_id": "rebuttals",
  "slides": [
    {{
      "slide_id": "rebuttals_1",
      "title": "Key Objections & Responses",
      "bullets": [
        {{"text": "Q: [Tough question] → A: [Response]", "source_needed": false}},
        {{"text": "Q: [Another question] → A: [Response]", "source_needed": false}},
        {{"text": "Q: [Another question] → A: [Response]", "source_needed": false}}
      ],
      "speaker_notes": "Expanded talking points for each objection...",
      "layout_hints": {{"style": "qa_format", "max_bullets": 4}},
      "flags": {{"needs_sources": false, "contains_numbers": false, "is_draft": false}}
    }}
  ]
}}"""


def get_layout_prompt(
    ticker: str,
    company_name: str,
    sector: str,
    fund_constraints: dict,
    requested_sections: list[str],
) -> str:
    """Generate prompt for Layout Decisions section."""
    
    sections_list = ", ".join(requested_sections)
    
    return f"""Generate Layout Decisions and Presentation Guidance for the {company_name} ({ticker}) pitch deck.

CONTEXT:
- Fund Style: {fund_constraints.get('style', 'Student investment fund pitch')}
- Sections to present: {sections_list}

REQUIRED CONTENT:
Provide guidance on:

1. RECOMMENDED SLIDE ORDER
   - Logical flow for the presentation
   - Transitions between sections

2. VISUAL GUIDELINES
   - Color scheme suggestions (if applicable)
   - Chart/graph recommendations by section
   - Data visualization best practices

3. PRESENTER NOTES GUIDANCE
   - Time allocation per section
   - Key emphasis points
   - Handling Q&A

4. BULLET FORMATTING RULES
   - Maximum bullets per slide (4)
   - Parallel structure guidelines
   - Action-oriented language

Generate 1 slide summarizing the layout decisions and presenter guidance.

Respond with JSON:
{{
  "section_id": "layout",
  "slides": [
    {{
      "slide_id": "layout_1",
      "title": "Presentation Structure & Guidelines",
      "bullets": [
        {{"text": "Recommended order: [Section flow]", "source_needed": false}},
        {{"text": "Time allocation: [Guidance]", "source_needed": false}},
        {{"text": "Key emphasis: [What to highlight]", "source_needed": false}},
        {{"text": "Visual notes: [Chart/graph suggestions]", "source_needed": false}}
      ],
      "speaker_notes": "Detailed presenter guidance including timing, transitions, and Q&A handling...",
      "layout_hints": {{"style": "bullets", "max_bullets": 4}},
      "flags": {{"needs_sources": false, "contains_numbers": false, "is_draft": false}}
    }}
  ]
}}"""


# =============================================================================
# PROMPT FACTORY
# =============================================================================

SECTION_PROMPT_MAP = {
    "overview": get_overview_prompt,
    "history": get_history_prompt,
    "swot": get_swot_prompt,
    "porters_five": get_porters_five_prompt,
    "rebuttals": get_rebuttals_prompt,
    "layout": get_layout_prompt,
}


def get_section_prompt(
    section_id: str,
    ticker: str,
    company_name: str,
    sector: str,
    fund_constraints: dict,
    comps_summary: Optional[str] = None,
    requested_sections: Optional[list[str]] = None,
) -> str:
    """
    Get the appropriate prompt for a section.
    
    Args:
        section_id: Section identifier
        ticker: Stock ticker
        company_name: Company name
        sector: Industry sector
        fund_constraints: Fund constraint dict
        comps_summary: Optional formatted comps data
        requested_sections: List of all requested sections (for layout)
        
    Returns:
        Formatted prompt string
    """
    prompt_func = SECTION_PROMPT_MAP.get(section_id)
    if not prompt_func:
        raise ValueError(f"Unknown section ID: {section_id}")
    
    # Different sections need different arguments
    if section_id in ["overview", "swot"]:
        return prompt_func(ticker, company_name, sector, fund_constraints, comps_summary)
    elif section_id == "layout":
        return prompt_func(
            ticker, company_name, sector, fund_constraints,
            requested_sections or ["overview", "swot", "rebuttals"]
        )
    else:
        return prompt_func(ticker, company_name, sector, fund_constraints)


def get_fix_prompt(
    original_output: str,
    errors: list[str],
    schema: dict,
) -> str:
    """
    Generate a prompt to fix invalid LLM output.
    
    Args:
        original_output: The invalid output
        errors: List of validation errors
        schema: Expected JSON schema
        
    Returns:
        Fix prompt string
    """
    import json
    
    error_list = "\n".join(f"- {e}" for e in errors)
    
    return f"""Your previous response had validation errors. Please fix and respond with valid JSON only.

ERRORS FOUND:
{error_list}

REQUIREMENTS:
1. Fix all listed errors
2. Respond with ONLY the JSON object
3. No markdown code blocks
4. No explanations
5. Maximum 4 bullets per slide
6. All required fields must be present

YOUR PREVIOUS OUTPUT (truncated):
{original_output[:1500]}

Please provide the corrected JSON response now:"""
