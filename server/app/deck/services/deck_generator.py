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
        timeout: int = 120,
        use_cache: bool = True,
        parallel_sections: bool = True,  # Parallel for faster generation
        max_parallel_workers: int = 3,   # Keep moderate to avoid rate limits
        section_delay_seconds: float = 0.5,  # Delay between sequential sections
    ):
        self.max_retries = max_retries
        self.timeout = timeout
        self.use_cache = use_cache
        self.parallel_sections = parallel_sections
        self.max_parallel_workers = max(1, int(max_parallel_workers))
        self.section_delay_seconds = max(0.0, float(section_delay_seconds))


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
        api_keys: Optional[dict[str, Optional[str]]] = None,
        openai_api_key: Optional[str] = None,
        gemini_api_key: Optional[str] = None,
    ) -> DeckGenerateResponse:
        """
        Generate deck sections based on request.
        
        Args:
            request: Validated generation request
            api_keys: Dict of provider->key (preferred)
            openai_api_key: OpenAI API key (legacy, used if api_keys is None)
            gemini_api_key: Gemini API key (legacy, used if api_keys is None)
            
        Returns:
            DeckGenerateResponse with generated sections
        """
        # Normalise to dict form
        if api_keys is None:
            api_keys = {
                "openai": openai_api_key,
                "gemini": gemini_api_key,
            }
        request_id = str(uuid.uuid4())[:8]
        set_request_context(
            request_id=request_id,
            ticker=request.ticker,
            provider=request.provider.value,
        )
        
        logger.info(f"Starting deck generation", extra={
            "sections": request.sections,
            "include_comps": request.include_comps,
            "include_dcf": getattr(request, 'include_dcf', True),
        })
        
        start_time = time.time()
        
        # Build fallback chain from model_policy (if available)
        fallback_chain: list[tuple[str, str]] = []  # [(provider_name, model_id), ...]
        try:
            from app.deck.services.model_policy import resolve_model
            decision = resolve_model(
                plan_tier=getattr(request, "plan_tier", "free") or "free",
                analysis_depth=getattr(request, "analysis_depth", "medium") or "medium",
                model_mode="specific",
                requested_model_id=request.model,
                thinking_requested=request.reasoning_level.value == "high",
                available_keys=api_keys,
            )
            fallback_chain = [(m.provider, m.model_id) for m in decision.fallback_chain]
        except Exception:
            pass  # graceful degradation — no fallback

        # Get API key for provider
        api_key = self._get_api_key(request.provider.value, api_keys)
        
        # Initialize provider (with fallback on init failure)
        provider = get_provider(
            request.provider.value,
            api_key,
            request.model,
        )
        
        # Get comps data if requested
        comps_data = None
        comps_summary = None
        comps_concise = None
        if request.include_comps:
            try:
                comps_data = comps_service.get_comps_table(
                    ticker=request.ticker,
                    sector=request.sector,
                    comp_tickers=getattr(request, 'comp_tickers', None),
                )
                comps_summary = comps_service.format_for_prompt(comps_data)
                comps_concise = comps_service.format_for_prompt_concise(comps_data)
            except Exception as e:
                logger.warning(f"Failed to fetch comps: {e}")
        
        # Get DCF valuation if requested (default True)
        dcf_data = None
        dcf_summary = None
        dcf_detailed = None
        if getattr(request, 'include_dcf', True):
            try:
                from app.deck.services.dcf_calculator import calculate_dcf
                dcf_result = calculate_dcf(ticker=request.ticker)
                if not dcf_result.get("error"):
                    dcf_data = dcf_result
                    dcf_summary = self._format_dcf_for_prompt(dcf_result)
                    dcf_detailed = self._format_dcf_detailed(dcf_result)
                else:
                    logger.warning(f"DCF calculation error: {dcf_result.get('error')}")
            except Exception as e:
                logger.warning(f"Failed to calculate DCF: {e}")
        
        # Generate constraints hash for caching
        constraints_hash = compute_constraints_hash(request.fund_constraints.model_dump())
        
        # Generate each section IN PARALLEL for significant speedup
        results = []
        errors = []
        
        model_used = provider.get_model(request.model)
        
        # Import fallback-eligible errors
        from app.deck.services.llm_base import (
            AuthenticationError as LLMAuthError,
            RateLimitError as LLMRateLimitError,
            TimeoutError as LLMTimeoutError,
        )

        # Prepare generation tasks
        def generate_section_task(section_id: str):
            """Task wrapper for parallel execution with fallback."""
            dcf_for_section = dcf_detailed if section_id == "valuation" else dcf_summary
            comps_for_section = comps_concise if section_id in ["bull_case", "bear_case"] else comps_summary

            # Build list of (provider_instance, model_name) to try
            primary_extra = self._build_provider_options_extra(
                provider_name=provider.PROVIDER_NAME,
                model=model_used,
                reasoning_level=request.reasoning_level.value,
            )
            attempts: list[tuple] = [(provider, model_used, primary_extra)]
            for fb_provider_name, fb_model_id in fallback_chain:
                try:
                    fb_key = self._get_api_key(fb_provider_name, api_keys)
                    fb_prov = get_provider(fb_provider_name, fb_key, fb_model_id)
                    fb_model = fb_prov.get_model(fb_model_id)
                    fb_extra = self._build_provider_options_extra(
                        provider_name=fb_provider_name,
                        model=fb_model,
                        reasoning_level=request.reasoning_level.value,
                    )
                    attempts.append((fb_prov, fb_model, fb_extra))
                except Exception:
                    continue

            last_error: Optional[Exception] = None
            for attempt_idx, (cur_provider, cur_model, cur_extra) in enumerate(attempts):
                try:
                    result = self._generate_section(
                        provider=cur_provider,
                        section_id=section_id,
                        ticker=request.ticker,
                        company_name=request.company_name,
                        sector=request.sector,
                        fund_constraints=request.fund_constraints.model_dump(),
                        reasoning_level=request.reasoning_level.value,
                        comps_summary=comps_for_section,
                        dcf_summary=dcf_for_section,
                        requested_sections=request.sections,
                        constraints_hash=constraints_hash,
                        model=cur_model,
                        options_extra=cur_extra,
                        computed_inputs=comps_data,
                    )
                    if attempt_idx > 0:
                        logger.info(
                            f"Section {section_id} succeeded on fallback "
                            f"provider {cur_provider.PROVIDER_NAME}/{cur_model}"
                        )
                    return ('success', section_id, result)

                except (LLMAuthError, LLMRateLimitError, LLMTimeoutError) as e:
                    last_error = e
                    logger.warning(
                        f"Provider {cur_provider.PROVIDER_NAME} failed for "
                        f"{section_id}: {e}. Trying next fallback..."
                    )
                    continue

                except LLMError as e:
                    last_error = e
                    logger.error(f"Failed to generate section {section_id}: {e}")
                    break  # non-retriable LLM error

                except Exception as e:
                    last_error = e
                    logger.error(f"Unexpected error for section {section_id}: {e}", exc_info=True)
                    break

            # All attempts exhausted
            err = last_error or Exception("Unknown error")
            return ('error', section_id, GenerationError(
                section_id=section_id,
                error_type=type(err).__name__,
                message=str(err),
                retries_attempted=self.config.max_retries,
            ))
        
        if self.config.parallel_sections and len(request.sections) > 1:
            # Execute sections in parallel when explicitly enabled.
            max_workers = min(self.config.max_parallel_workers, len(request.sections))
            logger.info(
                f"Generating {len(request.sections)} sections in parallel with {max_workers} workers"
            )

            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                # Submit all tasks
                future_to_section = {
                    executor.submit(generate_section_task, section_id): section_id
                    for section_id in request.sections
                }

                # Collect results as they complete
                for future in as_completed(future_to_section):
                    status, section_id, result = future.result()
                    if status == 'success':
                        results.append(result)
                        logger.info(f"✓ Section {section_id} completed")
                    else:
                        errors.append(result)
                        logger.warning(f"✗ Section {section_id} failed")
        else:
            # Safer default for providers/accounts with strict request-per-minute limits.
            logger.info(f"Generating {len(request.sections)} sections sequentially")
            for idx, section_id in enumerate(request.sections):
                # Inter-section delay to reduce rate-limit hits (skip before first)
                if idx > 0 and self.config.section_delay_seconds > 0:
                    time.sleep(self.config.section_delay_seconds)
                status, section_id, result = generate_section_task(section_id)
                if status == 'success':
                    results.append(result)
                    logger.info(f"✓ Section {section_id} completed")
                else:
                    errors.append(result)
                    logger.warning(f"✗ Section {section_id} failed")
        
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
            company_name=request.company_name,
            plan_tier=getattr(request, "plan_tier", None),
            model_mode=getattr(request, "model_mode", None),
            analysis_depth=getattr(request, "analysis_depth", None),
            provider_used=ProviderInfo(
                provider=request.provider.value,
                model=model_used,
                reasoning_level=request.reasoning_level.value,
            ),
            generated_at=datetime.utcnow().isoformat() + "Z",
            computed_inputs=ComputedInputs(
                comps_table=comps_data if comps_data else None,
                dcf_valuation=dcf_data if dcf_data else None,
            ),
            results=results,
            errors=errors,
            request_id=request_id,
        )
    
    def _get_api_key(
        self,
        provider: str,
        api_keys: dict[str, Optional[str]],
    ) -> str:
        """Get API key for provider from the keys dict, checking environment as fallback."""
        import os

        # Env-var fallback map
        env_fallbacks: dict[str, list[str]] = {
            "openai": ["OPENAI_API_KEY"],
            "gemini": ["GEMINI_API_KEY", "GOOGLE_API_KEY"],
            "deepseek": ["DEEPSEEK_API_KEY"],
            "zai": ["ZAI_API_KEY"],
            "anthropic": ["ANTHROPIC_API_KEY"],
        }

        key = api_keys.get(provider)
        if not key:
            for env_name in env_fallbacks.get(provider, []):
                key = os.getenv(env_name)
                if key:
                    break

        if not key:
            raise ValueError(
                f"{provider} API key required. "
                f"Set one of {env_fallbacks.get(provider, [provider.upper() + '_API_KEY'])}."
            )
        return key

    def _build_provider_options_extra(
        self,
        provider_name: str,
        model: str,
        reasoning_level: str,
    ) -> dict[str, Any]:
        """Build provider-specific generation options from a common reasoning level.

        The caller supplies `reasoning_level` as low/medium/high. This method maps
        that into each provider's native controls based on official provider docs.
        """
        level = (reasoning_level or "medium").lower()
        provider = provider_name.lower()
        model_lc = (model or "").lower()

        # OpenAI Chat Completions supports reasoning_effort for reasoning models.
        if provider == "openai":
            effort = "high" if level == "high" else ("low" if level == "low" else "medium")
            return {"model": model, "reasoning_effort": effort}

        # Gemini thinking controls vary by model family.
        # - Gemini 3 Pro: supports low/high.
        # - Gemini 3 Flash: supports low/medium/high (plus minimal, not exposed here).
        if provider == "gemini":
            if "gemini-3-pro" in model_lc:
                thinking_level = "high" if level in {"medium", "high"} else "low"
            else:
                thinking_level = "high" if level == "high" else ("low" if level == "low" else "medium")
            return {"model": model, "thinking_level": thinking_level}

        # DeepSeek thinking mode is model-level: deepseek-chat vs deepseek-reasoner.
        if provider == "deepseek":
            return {"model": model}

        # Z.AI uses thinking={"type":"enabled"|"disabled"}.
        if provider == "zai":
            return {
                "model": model,
                "thinking_enabled": level in {"medium", "high"},
            }

        # Anthropic uses extended thinking with budget tokens.
        if provider == "anthropic":
            if level == "high":
                return {
                    "model": model,
                    "thinking_enabled": True,
                    "thinking_budget_tokens": 10_000,
                }
            if level == "medium":
                return {
                    "model": model,
                    "thinking_enabled": True,
                    "thinking_budget_tokens": 4_000,
                }
            return {"model": model, "thinking_enabled": False}

        return {"model": model}
    
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
        dcf_summary: Optional[str],
        requested_sections: list[str],
        constraints_hash: str,
        model: str,
        options_extra: Optional[dict[str, Any]] = None,
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
            dcf_summary: Optional DCF valuation summary for prompt
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
            dcf_summary=dcf_summary,
            requested_sections=requested_sections,
        )
        
        # Get schema for section
        schema = get_section_schema(section_id)
        
        # Build options
        options = LLMOptions(
            reasoning_level=reasoning_level,
            timeout=self.config.timeout,
            extra=options_extra or {},
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
        
        # Get section name from metadata
        section_metadata = SECTION_METADATA.get(section_id, {})
        section_name = section_metadata.get("label", section_id)
        
        return SectionResult(
            section_id=section_id,
            section_name=section_name,
            slides=slides,
            needs_verification=content.get("needs_verification", False),
            verification_notes=content.get("verification_notes", []),
            citations=[],  # Always empty - LLM cannot provide citations
        )
    
    def plan_deck(
        self,
        request: DeckPlanRequest,
        api_keys: Optional[dict[str, Optional[str]]] = None,
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
            SectionId.BULL_CASE,
            SectionId.BEAR_CASE,
            SectionId.VALUATION,
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
            "valuation": "Quantitative DCF analysis with transparent methodology and assumptions",
            "rebuttals": "Prepares the team for tough questions during Q&A",
            "layout": "Provides presentation guidance and structure recommendations",
        }
        
        base = rationales.get(section_id, "Standard pitch deck component")
        
        # Customize based on constraints
        if fund_constraints.get("risk_profile") == "conservative" and section_id in ["swot", "rebuttals"]:
            base += ". Especially important given conservative risk profile."
        
        return base
    
    def _format_dcf_for_prompt(self, dcf_data: dict) -> str:
        """
        Format DCF data for prompt (concise version for bull/bear sections).
        
        Args:
            dcf_data: DCF data dictionary
            
        Returns:
            Formatted string for prompt
        """
        val = dcf_data.get("valuation", {})
        target = val.get("targetPrice")
        upside = val.get("upsidePct")
        
        if target and upside is not None:
            return f"DCF Target: ${target:.2f} ({upside:+.1f}% vs market)"
        return ""
    
    def _format_dcf_detailed(self, dcf_data: dict) -> str:
        """
        Format DCF data with full details for valuation section.
        
        Args:
            dcf_data: DCF data dictionary
            
        Returns:
            Detailed formatted string with all DCF components
        """
        if not dcf_data:
            return ""
        
        inputs = dcf_data.get("inputs", {})
        val = dcf_data.get("valuation", {})
        breakdown = dcf_data.get("breakdown", {})
        sources = dcf_data.get("sources", {})
        
        lines = ["DCF CALCULATION BREAKDOWN:"]
        
        # Inputs
        lines.append("\nINPUTS (sourced from yfinance):")
        if "freeCashFlow" in inputs:
            lines.append(f"  - Free Cash Flow: ${inputs['freeCashFlow']/1e9:.2f}B")
        if "growthRate" in inputs:
            lines.append(f"  - Growth Rate: {inputs['growthRate']*100:.1f}%")
        if "discountRate" in inputs:
            lines.append(f"  - Discount Rate (WACC): {inputs['discountRate']*100:.1f}%")
        if "terminalGrowthRate" in inputs:
            lines.append(f"  - Terminal Growth Rate: {inputs['terminalGrowthRate']*100:.1f}%")
        
        # Calculation steps
        if breakdown:
            lines.append("\nCALCULATION STEPS:")
            if "forecastPeriodPV" in breakdown:
                lines.append(f"  - Forecast Period PV: ${breakdown['forecastPeriodPV']/1e9:.2f}B")
            if "terminalValue" in breakdown:
                lines.append(f"  - Terminal Value: ${breakdown['terminalValue']/1e9:.2f}B")
            if "enterpriseValue" in breakdown:
                lines.append(f"  - Enterprise Value: ${breakdown['enterpriseValue']/1e9:.2f}B")
            if "equityValue" in breakdown:
                lines.append(f"  - Equity Value: ${breakdown['equityValue']/1e9:.2f}B")
        
        # Target price
        lines.append("\nTARGET PRICE:")
        if "currentPrice" in val:
            lines.append(f"  - Current Price: ${val['currentPrice']:.2f}")
        if "targetPrice" in val:
            lines.append(f"  - DCF Target Price: ${val['targetPrice']:.2f}")
        if "upsidePct" in val:
            lines.append(f"  - Implied Upside: {val['upsidePct']:+.1f}%")
        
        # Sources
        if sources:
            lines.append("\nDATA SOURCES:")
            for key, source in sources.items():
                lines.append(f"  - {key}: {source}")
        
        return "\n".join(lines)
    


# Singleton generator instance
deck_generator = DeckGenerator()
