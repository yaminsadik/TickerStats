"""
Deck Generator Orchestrator.
Coordinates LLM providers, prompts, and validation for slide generation.
"""

import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Any, Optional

from app.deck.api.schemas import (
    SECTION_METADATA,
    BulletPoint,
    ComputedInputs,
    DeckGenerateRequest,
    DeckGenerateResponse,
    DeckPlanRequest,
    DeckPlanResponse,
    GenerationError,
    LayoutHints,
    ProviderInfo,
    SectionId,
    SectionResult,
    Slide,
    SlideFlags,
    SuggestedSection,
    get_section_schema,
)
from app.deck.services.comps_service import comps_service
from app.deck.services.llm_base import (
    LLMError,
    LLMOptions,
    LLMProvider,
    LLMResponse,
    get_provider,
)
from app.deck.services.prompts import (
    SYSTEM_PROMPT,
    get_fix_prompt,
    get_section_prompt,
)
from app.deck.utils.cache import get_cache
from app.deck.utils.logging import get_logger, log_operation, set_request_context
from app.deck.utils.validation import (
    compute_constraints_hash,
    flag_numeric_content,
    has_unverified_numbers,
    validate_section_output,
)

logger = get_logger(__name__)


class DeckGeneratorConfig:
    """Configuration for deck generator."""
    
    def __init__(
        self,
        max_retries: int = 2,
        timeout: int = 60,
        use_cache: bool = True,
        parallel_sections: bool = False,  # Sequential by default for rate limits
    ):
        self.max_retries = max_retries
        self.timeout = timeout
        self.use_cache = use_cache
        self.parallel_sections = parallel_sections


class DeckGenerator:
    """
    Orchestrates deck slide generation using LLM providers.
    
    Responsibilities:
    - Coordinate section generation with appropriate prompts
    - Handle retries and validation
    - Manage caching
    - Format responses
    """
    
    def __init__(self, config: Optional[DeckGeneratorConfig] = None):
        self.config = config or DeckGeneratorConfig()
        self._cache = get_cache()
    
    def generate_deck(
        self,
        request: DeckGenerateRequest,
        openai_api_key: Optional[str] = None,
        gemini_api_key: Optional[str] = None,
    ) -> DeckGenerateResponse:
        """
        Generate deck sections based on request.
        
        Args:
            request: Validated generation request
            openai_api_key: OpenAI API key (required if provider=openai)
            gemini_api_key: Gemini API key (required if provider=gemini)
            
        Returns:
            DeckGenerateResponse with generated sections
        """
        request_id = str(uuid.uuid4())[:8]
        set_request_context(
            request_id=request_id,
            ticker=request.ticker,
            provider=request.provider.value,
        )
        
        logger.info(f"Starting deck generation", extra={
            "sections": request.sections,
            "include_comps": request.include_comps,
        })
        
        start_time = time.time()
        
        # Get API key for provider
        api_key = self._get_api_key(request.provider.value, openai_api_key, gemini_api_key)
        
        # Initialize provider
        provider = get_provider(
            request.provider.value,
            api_key,
            request.model,
        )
        
        # Get comps data if requested
        comps_data = None
        comps_summary = None
        if request.include_comps:
            try:
                comps_data = comps_service.get_comps_table(
                    ticker=request.ticker,
                    sector=request.sector,
                )
                comps_summary = comps_service.format_for_prompt(comps_data)
            except Exception as e:
                logger.warning(f"Failed to fetch comps: {e}")
        
        # Generate constraints hash for caching
        constraints_hash = compute_constraints_hash(request.fund_constraints.model_dump())
        
        # Generate each section
        results = []
        errors = []
        
        model_used = provider.get_model(request.model)
        
        for section_id in request.sections:
            try:
                result = self._generate_section(
                    provider=provider,
                    section_id=section_id,
                    ticker=request.ticker,
                    company_name=request.company_name,
                    sector=request.sector,
                    fund_constraints=request.fund_constraints.model_dump(),
                    reasoning_level=request.reasoning_level.value,
                    comps_summary=comps_summary,
                    requested_sections=request.sections,
                    constraints_hash=constraints_hash,
                    model=model_used,
                    computed_inputs=comps_data,  # Pass computed data for numbers gate
                )
                results.append(result)
                
            except LLMError as e:
                logger.error(f"Failed to generate section {section_id}: {e}")
                errors.append(GenerationError(
                    section_id=section_id,
                    error_type=type(e).__name__,
                    message=str(e),
                    retries_attempted=self.config.max_retries,
                ))
            except Exception as e:
                logger.error(f"Unexpected error for section {section_id}: {e}", exc_info=True)
                errors.append(GenerationError(
                    section_id=section_id,
                    error_type="UnexpectedError",
                    message=str(e),
                    retries_attempted=0,
                ))
        
        total_time = time.time() - start_time
        logger.info(f"Deck generation complete", extra={
            "total_time_ms": round(total_time * 1000, 2),
            "sections_generated": len(results),
            "errors": len(errors),
        })

        if not results and not errors:
            errors.append(GenerationError(
                section_id="all",
                error_type="NoSectionsGenerated",
                message=(
                    "No sections were generated. Check provider configuration, "
                    "API key, and server logs for details."
                ),
                retries_attempted=0,
            ))
        
        return DeckGenerateResponse(
            ticker=request.ticker,
            provider_used=ProviderInfo(
                provider=request.provider.value,
                model=model_used,
                reasoning_level=request.reasoning_level.value,
            ),
            generated_at=datetime.utcnow().isoformat() + "Z",
            computed_inputs=ComputedInputs(
                comps_table=comps_data if comps_data else None,
            ),
            results=results,
            errors=errors,
            request_id=request_id,
        )
    
    def _get_api_key(
        self,
        provider: str,
        openai_key: Optional[str],
        gemini_key: Optional[str],
    ) -> str:
        """Get API key for provider, checking environment as fallback."""
        import os
        
        if provider == "openai":
            key = openai_key or os.getenv("OPENAI_API_KEY")
            if not key:
                raise ValueError("OpenAI API key required. Set OPENAI_API_KEY or pass openai_api_key.")
            return key
        elif provider == "gemini":
            key = gemini_key or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
            if not key:
                raise ValueError("Gemini API key required. Set GEMINI_API_KEY or pass gemini_api_key.")
            return key
        else:
            raise ValueError(f"Unknown provider: {provider}")
    
    @log_operation("generate_section")
    def _generate_section(
        self,
        provider: LLMProvider,
        section_id: str,
        ticker: str,
        company_name: str,
        sector: str,
        fund_constraints: dict,
        reasoning_level: str,
        comps_summary: Optional[str],
        requested_sections: list[str],
        constraints_hash: str,
        model: str,
        computed_inputs: Optional[dict] = None,
    ) -> SectionResult:
        """
        Generate a single deck section.
        
        Args:
            provider: LLM provider instance
            section_id: Section to generate
            ticker: Stock ticker
            company_name: Company name
            sector: Industry sector
            fund_constraints: Fund constraints dict
            reasoning_level: Reasoning intensity
            comps_summary: Optional comps data for prompt
            requested_sections: All requested sections
            constraints_hash: Hash for caching
            model: Model name
            computed_inputs: Optional dict of computed data for numbers gate
            
        Returns:
            SectionResult with generated slides
        """
        # Check cache
        if self.config.use_cache:
            cached = self._cache.get_section(
                ticker, section_id, provider.PROVIDER_NAME, model, constraints_hash
            )
            if cached:
                logger.info(f"Cache hit for section {section_id}")
                return SectionResult(**cached)
        
        # Build prompt
        prompt = get_section_prompt(
            section_id=section_id,
            ticker=ticker,
            company_name=company_name,
            sector=sector,
            fund_constraints=fund_constraints,
            comps_summary=comps_summary,
            requested_sections=requested_sections,
        )
        
        # Get schema for section
        schema = get_section_schema(section_id)
        
        # Build options
        options = LLMOptions(
            reasoning_level=reasoning_level,
            timeout=self.config.timeout,
        )
        
        # Generate with retry
        response = provider.generate_with_retry(
            system_prompt=SYSTEM_PROMPT,
            user_prompt=prompt,
            json_schema=schema,
            options=options,
            max_retries=self.config.max_retries,
            fix_prompt_builder=get_fix_prompt,
        )
        
        # Validate and transform response with numbers gate
        result = self._transform_section_response(
            response.content,
            section_id,
            computed_inputs=computed_inputs,
        )
        result.generation_metadata = {
            "model": response.model,
            "latency_ms": response.latency_ms,
            "retries": response.retries,
            "tokens": response.usage,
        }
        
        # Cache result
        if self.config.use_cache:
            self._cache.set_section(
                ticker, section_id, provider.PROVIDER_NAME, model,
                constraints_hash, result.model_dump()
            )
        
        return result
    
    def _transform_section_response(
        self,
        content: dict,
        section_id: str,
        computed_inputs: Optional[dict] = None,
    ) -> SectionResult:
        """
        Transform raw LLM response into validated SectionResult.
        
        Applies strict "no fabricated numbers" gate: any numeric content
        not traceable to computed_inputs gets flagged with needs_sources=True.
        
        Args:
            content: Raw content from LLM
            section_id: Section identifier
            computed_inputs: Optional dict of computed data (comps, etc.)
            
        Returns:
            Validated SectionResult
        """
        # Validate
        validation = validate_section_output(content, section_id)
        if not validation.valid:
            logger.warning(f"Section output validation issues: {validation.errors}")
        
        # Transform slides
        slides = []
        for slide_data in content.get("slides", []):
            # Get bullets and apply numbers gate
            raw_bullets = slide_data.get("bullets", [])
            
            # Normalize bullets to dict format
            normalized_bullets = []
            for bullet in raw_bullets:
                if isinstance(bullet, str):
                    normalized_bullets.append({"text": bullet, "source_needed": False})
                else:
                    normalized_bullets.append(bullet)
            
            # Apply strict numbers gate - flags bullets with unverified numbers
            checked_bullets = flag_numeric_content(normalized_bullets, computed_inputs)
            
            # Convert to BulletPoint objects
            bullets = [
                BulletPoint(
                    text=b.get("text", ""),
                    source_needed=b.get("source_needed", False),
                )
                for b in checked_bullets
            ]
            
            # Transform layout hints
            hints_data = slide_data.get("layout_hints", {})
            layout_hints = LayoutHints(
                style=hints_data.get("style", "bullets"),
                max_bullets=hints_data.get("max_bullets", 4),
                suggested_visual=hints_data.get("suggested_visual"),
            )
            
            # Transform flags
            flags_data = slide_data.get("flags", {})
            
            # Determine if any bullets need sources (from numbers gate)
            any_needs_sources = any(b.source_needed for b in bullets)
            
            # Determine if slide contains numbers
            contains_nums = any(
                has_unverified_numbers(b.text, computed_inputs) or 
                bool(flags_data.get("contains_numbers"))
                for b in bullets
            )
            
            flags = SlideFlags(
                needs_sources=flags_data.get("needs_sources", False) or any_needs_sources,
                contains_numbers=contains_nums or flags_data.get("contains_numbers", False),
                is_draft=flags_data.get("is_draft", False),
            )
            
            slides.append(Slide(
                slide_id=slide_data.get("slide_id", f"{section_id}_{len(slides) + 1}"),
                title=slide_data.get("title", ""),
                bullets=bullets[:4],  # Enforce max 4
                speaker_notes=slide_data.get("speaker_notes", ""),
                layout_hints=layout_hints,
                flags=flags,
            ))
        
        return SectionResult(
            section_id=section_id,
            slides=slides,
            needs_verification=content.get("needs_verification", False),
            verification_notes=content.get("verification_notes", []),
            citations=[],  # Always empty - LLM cannot provide citations
        )
    
    def plan_deck(
        self,
        request: DeckPlanRequest,
        openai_api_key: Optional[str] = None,
        gemini_api_key: Optional[str] = None,
    ) -> DeckPlanResponse:
        """
        Generate a deck plan with suggested sections and ordering.
        
        Args:
            request: Plan request
            openai_api_key: OpenAI API key
            gemini_api_key: Gemini API key
            
        Returns:
            DeckPlanResponse with suggested sections
        """
        request_id = str(uuid.uuid4())[:8]
        set_request_context(request_id=request_id, ticker=request.ticker)
        
        logger.info("Generating deck plan")
        
        # For planning, we use a simplified approach based on section metadata
        # In a production system, this could use LLM to analyze the company
        
        suggested = []
        
        # Standard ordering based on presentation flow
        standard_order = [
            SectionId.OVERVIEW,
            SectionId.HISTORY,
            SectionId.SWOT,
            SectionId.PORTERS_FIVE,
            SectionId.REBUTTALS,
            SectionId.LAYOUT,
        ]
        
        for i, section_id in enumerate(standard_order):
            meta = SECTION_METADATA.get(section_id, {})
            
            # Generate rationale based on section type and fund constraints
            rationale = self._generate_plan_rationale(
                section_id.value,
                request.sector,
                request.fund_constraints.model_dump(),
            )
            
            suggested.append(SuggestedSection(
                id=section_id.value,
                label=meta.get("label", section_id.value),
                priority=i + 1,
                rationale=rationale,
                estimated_slides=meta.get("max_slides", 2),
            ))
        
        return DeckPlanResponse(
            ticker=request.ticker,
            company_name=request.company_name or request.ticker,
            suggested_sections=suggested,
            recommended_order=[s.id for s in suggested],
            notes=f"Standard investment pitch deck structure for {request.sector} sector.",
            request_id=request_id,
        )
    
    def _generate_plan_rationale(
        self,
        section_id: str,
        sector: str,
        fund_constraints: dict,
    ) -> str:
        """Generate rationale for including a section."""
        rationales = {
            "overview": f"Essential for introducing the {sector} investment thesis",
            "history": "Provides context on company evolution and key milestones",
            "swot": "Critical framework for evaluating investment merit and risks",
            "porters_five": f"Important for understanding {sector} competitive dynamics",
            "rebuttals": "Prepares the team for tough questions during Q&A",
            "layout": "Provides presentation guidance and structure recommendations",
        }
        
        base = rationales.get(section_id, "Standard pitch deck component")
        
        # Customize based on constraints
        if fund_constraints.get("risk_profile") == "conservative" and section_id in ["swot", "rebuttals"]:
            base += ". Especially important given conservative risk profile."
        
        return base


# Singleton generator instance
deck_generator = DeckGenerator()
