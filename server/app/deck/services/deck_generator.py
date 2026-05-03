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
    get_section_metadata,
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
)
from app.deck.services.sections import ALL_SECTIONS, get_section
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
        
        # Resolve data trust mode
        data_trust_mode = "user_auto_fetch"
        if getattr(request, "data_trust_mode", None):
            data_trust_mode = request.data_trust_mode.value

        # Map peer_tickers from valuation_input into comp_tickers for backward compat
        comp_tickers = getattr(request, "comp_tickers", None)
        if not comp_tickers and getattr(request, "valuation_input", None):
            peer = request.valuation_input.peer_tickers
            if peer:
                comp_tickers = peer

        # Get comps data if requested (skip for user_only / narrative_only)
        comps_data = None
        comps_summary = None
        if request.include_comps and data_trust_mode not in ("user_only", "narrative_only"):
            try:
                comps_data = comps_service.get_comps_table(
                    ticker=request.ticker,
                    sector=request.sector,
                    comp_tickers=comp_tickers,
                )
                comps_summary = comps_service.format_for_prompt(comps_data)
            except Exception as e:
                logger.warning(f"Failed to fetch comps: {e}")

        # Get DCF valuation if requested (skip for user_only / narrative_only)
        dcf_data = None
        dcf_summary = None
        if getattr(request, 'include_dcf', True) and data_trust_mode not in ("user_only", "narrative_only"):
            try:
                from app.deck.services.dcf_calculator import calculate_dcf
                dcf_result = calculate_dcf(ticker=request.ticker)
                if not dcf_result.get("error"):
                    dcf_data = dcf_result
                    dcf_summary = self._format_dcf_for_prompt(dcf_result)
                else:
                    logger.warning(f"DCF calculation error: {dcf_result.get('error')}")
            except Exception as e:
                logger.warning(f"Failed to calculate DCF: {e}")

        company_profile: dict[str, Any] = {
            "ticker": request.ticker,
            "name": request.company_name,
            "sector": request.sector,
        }
        try:
            from app.deck.utils.ticker_info import get_company_info

            fetched_profile = get_company_info(request.ticker)
            if fetched_profile:
                company_profile.update({
                    "name": fetched_profile.get("company_name") or request.company_name,
                    "sector": fetched_profile.get("sector") or request.sector,
                    "industry": fetched_profile.get("industry"),
                    "description": fetched_profile.get("description"),
                    "website": fetched_profile.get("website"),
                })
        except Exception as e:
            logger.warning(f"Failed to fetch company profile: {e}")

        resolved_company_name = str(
            company_profile.get("name") or request.company_name or request.ticker
        )
        
        # Generate a cache key from the full generation context, not just fund
        # constraints. This prevents stale sections after prompt/context changes
        # or after users change thesis, catalysts, data blocks, etc.
        try:
            request_cache_payload = request.model_dump(mode="json")
        except TypeError:
            request_cache_payload = request.model_dump()
        constraints_hash = compute_constraints_hash({
            "prompt_version": "company-profile-context-v1",
            "request": request_cache_payload,
            "company_profile": company_profile,
        })
        
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
            dcf_for_section = dcf_summary
            comps_for_section = comps_summary
            section_inputs = self._assemble_section_inputs(
                ticker=request.ticker,
                company_name=resolved_company_name,
                sector=request.sector,
                fund_constraints=request.fund_constraints.model_dump(),
                comps_summary=comps_for_section,
                dcf_summary=dcf_for_section,
                requested_sections=request.sections,
                company_profile=company_profile,
                request=request,
                comps_data=comps_data,
                dcf_data=dcf_data,
                comp_tickers=comp_tickers,
            )

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
                    numeric_gate_inputs: dict[str, Any] = {}
                    if comps_data:
                        numeric_gate_inputs["comps_table"] = comps_data
                    if dcf_data:
                        numeric_gate_inputs["dcf_valuation"] = dcf_data

                    result = self._generate_section(
                        provider=cur_provider,
                        section_id=section_id,
                        ticker=request.ticker,
                        company_name=resolved_company_name,
                        sector=request.sector,
                        fund_constraints=request.fund_constraints.model_dump(),
                        reasoning_level=request.reasoning_level.value,
                        comps_summary=comps_for_section,
                        dcf_summary=dcf_for_section,
                        requested_sections=request.sections,
                        constraints_hash=constraints_hash,
                        model=cur_model,
                        options_extra=cur_extra,
                        computed_inputs=numeric_gate_inputs,
                        section_inputs=section_inputs,
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

        if comps_data and not any(
            result.section_id in {"comparable_companies", "comparables"}
            for result in results
        ):
            results.append(
                SectionResult(
                    section_id="comparable_companies",
                    section_name="Comparable Companies",
                    slides=[
                        Slide(
                            slide_id="comparable_companies_1",
                            title="Comparable Companies",
                            bullets=[
                                BulletPoint(
                                    text="Comparable-company trading metrics from computed market data.",
                                    source_needed=False,
                                )
                            ],
                            speaker_notes="Renderer uses computed_inputs.comps_table for the full trading comps table.",
                            layout_hints=LayoutHints(
                                style="table",
                                max_bullets=1,
                                suggested_visual="comps_table",
                            ),
                            flags=SlideFlags(
                                needs_sources=False,
                                contains_numbers=True,
                                is_draft=False,
                            ),
                        )
                    ],
                    needs_verification=False,
                    verification_notes=[],
                    citations=[],
                    generation_metadata={"source": "computed_inputs.comps_table"},
                )
            )
        
        return DeckGenerateResponse(
            ticker=request.ticker,
            company_name=resolved_company_name,
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
        """Get provider credential marker from the keys dict, checking environment as fallback."""
        import os

        from app.core.config import settings

        if provider == "gemini" and settings.GOOGLE_GENAI_USE_VERTEXAI:
            if settings.GOOGLE_CLOUD_PROJECT and settings.GOOGLE_CLOUD_LOCATION:
                return api_keys.get(provider) or "__vertex_adc__"
            raise ValueError(
                "Gemini Vertex AI requires GOOGLE_CLOUD_PROJECT and GOOGLE_CLOUD_LOCATION."
            )

        # Env-var fallback map
        env_fallbacks: dict[str, list[str]] = {
            "gemini": ["GEMINI_API_KEY", "GOOGLE_API_KEY"],
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

        # Gemini Pro models support low/high thinking levels.
        if provider == "gemini":
            if "pro" in model_lc:
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

        return {"model": model}

    def _assemble_section_inputs(
        self,
        ticker: str,
        company_name: str,
        sector: str,
        fund_constraints: dict[str, Any],
        comps_summary: Optional[str],
        dcf_summary: Optional[str],
        requested_sections: list[str],
        company_profile: Optional[dict[str, Any]] = None,
        request: Optional[Any] = None,
        comps_data: Optional[dict[str, Any]] = None,
        dcf_data: Optional[dict[str, Any]] = None,
        comp_tickers: Optional[list[str]] = None,
    ) -> dict[str, Any]:
        """Assemble all inputs used by section prompt builders."""
        profile = company_profile or {}
        profile_name = profile.get("name") or company_name
        profile_sector = profile.get("sector") or sector
        profile_description = profile.get("description") or ""
        computed_inputs: dict[str, Any] = {}
        if comps_data:
            computed_inputs["comps_table"] = comps_data
        if dcf_data:
            computed_inputs["dcf_valuation"] = dcf_data

        inputs = {
            "ticker": ticker,
            "company_name": profile_name,
            "sector": profile_sector,
            "industry": profile.get("industry") or "",
            "description": profile_description,
            "company_description": profile_description,
            "business_description": profile_description,
            "company": {
                "ticker": ticker,
                "name": profile_name,
                "sector": profile_sector,
                "industry": profile.get("industry"),
                "description": profile_description,
                "website": profile.get("website"),
            },
            "fund_constraints": fund_constraints,
            "comps_summary": comps_summary,
            "dcf_summary": dcf_summary,
            "requested_sections": requested_sections,
            "comp_tickers": comp_tickers or [],
            "computed_inputs": computed_inputs,
            "comps_table": comps_data,
            "dcf_valuation": dcf_data,
        }
        # Intake redesign fields
        if request is not None:
            inputs["include_dcf"] = bool(getattr(request, "include_dcf", True))
            inputs["include_dcf_output"] = bool(getattr(request, "include_dcf", True))
            inputs["data_trust_mode"] = (
                request.data_trust_mode.value
                if getattr(request, "data_trust_mode", None)
                else "user_auto_fetch"
            )
            inputs["position"] = (
                request.position.value
                if getattr(request, "position", None)
                else None
            )
            inputs["deck_length"] = (
                request.deck_length.value
                if getattr(request, "deck_length", None)
                else "standard"
            )
            inputs["thesis"] = (
                request.thesis.model_dump()
                if getattr(request, "thesis", None)
                else None
            )
            inputs["catalysts"] = (
                [c.model_dump() for c in request.catalysts]
                if getattr(request, "catalysts", None)
                else []
            )
            valuation = (
                request.valuation_input.model_dump()
                if getattr(request, "valuation_input", None)
                else None
            )
            if comp_tickers:
                clean_peers = [
                    ticker_value.upper().strip()
                    for ticker_value in comp_tickers
                    if isinstance(ticker_value, str) and ticker_value.strip()
                ]
                if valuation is None:
                    valuation = {
                        "methods": ["relative"],
                        "peer_tickers": clean_peers,
                        "target_multiple_range": None,
                        "dcf_assumptions": None,
                        "price_target": None,
                    }
                else:
                    if not valuation.get("peer_tickers"):
                        valuation["peer_tickers"] = clean_peers
                    methods = list(valuation.get("methods") or [])
                    if valuation.get("peer_tickers") and "relative" not in methods:
                        methods.append("relative")
                    valuation["methods"] = methods
            inputs["valuation"] = valuation
            inputs["risks"] = (
                [r.model_dump() for r in request.risks]
                if getattr(request, "risks", None)
                else []
            )
            inputs["data_blocks"] = (
                request.data_blocks.model_dump()
                if getattr(request, "data_blocks", None)
                else None
            )
            inputs["user_constraints"] = (
                request.user_constraints.model_dump()
                if getattr(request, "user_constraints", None)
                else None
            )
        return inputs

    def _missing_required_context(
        self,
        inputs: dict[str, Any],
        required_context: set[str],
    ) -> list[str]:
        """Return required context keys that are absent or blank."""
        missing: list[str] = []
        for key in required_context:
            value = inputs.get(key)
            if value is None:
                missing.append(key)
                continue
            if isinstance(value, str) and not value.strip():
                missing.append(key)
        return missing

    def _build_prompt_and_schema(
        self,
        section_id: str,
        inputs: dict[str, Any],
    ) -> tuple[str, dict[str, Any], bool]:
        """
        Build prompt/schema for a section.

        Returns:
            tuple of (prompt, schema, used_registry)
        """
        if section_id not in ALL_SECTIONS:
            raise ValueError(f"Unknown section ID: {section_id}")

        spec = get_section(section_id)
        missing = self._missing_required_context(inputs, spec.required_context)
        if missing:
            missing_text = ", ".join(sorted(missing))
            raise ValueError(
                f"Missing required context for section '{section_id}': {missing_text}"
            )
        return spec.build_prompt(inputs), spec.schema, True
    
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
        section_inputs: Optional[dict[str, Any]] = None,
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
            section_inputs: Optional pre-assembled prompt inputs
            
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

        inputs = section_inputs or self._assemble_section_inputs(
            ticker=ticker,
            company_name=company_name,
            sector=sector,
            fund_constraints=fund_constraints,
            comps_summary=comps_summary,
            dcf_summary=dcf_summary,
            requested_sections=requested_sections,
        )
        
        # Build prompt + schema from the modular section registry.
        prompt, schema, used_registry = self._build_prompt_and_schema(section_id, inputs)
        
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

        content = response.content
        if used_registry:
            spec = get_section(section_id)
            if spec.postprocess is not None:
                content = spec.postprocess(content, inputs)
        
        # Validate and transform response with numbers gate
        result = self._transform_section_response(
            content,
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
            
            # Convert to BulletPoint objects (truncate to max_length to avoid crash)
            bullets = [
                BulletPoint(
                    text=b.get("text", "")[:500],
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
        section_metadata = get_section_metadata(section_id)
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
        
        suggested = []

        # Standard ordering for the modern modular section set.
        standard_order = [
            SectionId.COMPANY_SNAPSHOT,
            SectionId.OVERVIEW,
            SectionId.HISTORY,
            SectionId.BUSINESS_MODEL_SEGMENTS,
            SectionId.INDUSTRY_COMPETITIVE_LANDSCAPE,
            SectionId.HISTORICAL_PERFORMANCE_CURRENT_SETUP,
            SectionId.MANAGEMENT_OWNERSHIP_GOVERNANCE,
            SectionId.CAPITAL_STRUCTURE_FINANCIAL_HEALTH,
            SectionId.SWOT,
            SectionId.KEY_DRIVERS_KPIS,
            SectionId.SECTOR_INVARIANTS,
        ]
        
        for i, section_id in enumerate(standard_order):
            meta = get_section_metadata(section_id.value)
            
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
            "company_snapshot": "Establishes company identity, positioning, and business context in one institutional opening slide.",
            "overview": f"Essential for introducing the {sector} investment thesis",
            "history": "Provides context on company evolution and key milestones",
            "business_model_segments": "Clarifies revenue engine, customer segments, and unit economics.",
            "industry_competitive_landscape": f"Frames {sector} structure, competition, and moat durability.",
            "historical_performance_current_setup": "Connects multi-year operating trends with the current market setup.",
            "management_ownership_governance": "Assesses management track record, incentive alignment, ownership structure, and governance flags.",
            "capital_structure_financial_health": "Evaluates leverage, refinancing profile, liquidity runway, and dilution/capital-allocation risk.",
            "swot": "Stress-tests thesis quality through internal and external factors.",
            "key_drivers_kpis": "Identifies and defines the value-driving metrics that determine company performance and valuation.",
            "sector_invariants": f"Highlights sector-specific dynamics and dependencies critical to {sector} investment decisions.",
        }
        
        base = rationales.get(section_id, "Standard pitch deck component")
        
        # Customize based on constraints
        if fund_constraints.get("risk_profile") == "conservative" and section_id in ["swot", "historical_performance_current_setup"]:
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
    


# Singleton generator instance
deck_generator = DeckGenerator()
