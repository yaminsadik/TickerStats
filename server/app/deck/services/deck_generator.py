"""
Deck Generator Orchestrator.
Coordinates LLM providers, prompts, and validation for slide generation.
"""

import re
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Any, Optional

from app.deck.api.schemas import (
    AnalystConfidence,
    BulletPoint,
    ComputedInputs,
    DeckGenerateRequest,
    DeckGenerateResponse,
    DeckPlanRequest,
    DeckPlanResponse,
    DeckSectionsAnalysisResponse,
    GenerationError,
    LayoutHints,
    NarrativeTone,
    ProviderInfo,
    SectionId,
    SectionAnalysisControls,
    SectionAnalysisResult,
    SectionResult,
    Slide,
    SlideFlags,
    SuggestedSection,
    VisualPreference,
    WorkflowMode,
    get_section_metadata,
)
from app.deck.services.comps_service import comps_service
from app.deck.services.llm_base import (
    LLMError,
    LLMOptions,
    LLMProvider,
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


_EMPTY_TEXT_MARKERS = {
    "",
    "-",
    "—",
    "n/a",
    "na",
    "none",
    "null",
    "undefined",
    "unknown",
    "not provided",
    "not_provided",
    "tbd",
}

_PLACEHOLDER_PATTERN = re.compile(r"\b(not[_\s]+provided|null|none|undefined|tbd)\b", re.IGNORECASE)

SECTION_ANALYSIS_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": [
        "section_id",
        "section_name",
        "key_findings",
        "supporting_data_points",
        "risks_or_gaps",
        "recommended_storyline",
        "suggested_controls",
    ],
    "properties": {
        "section_id": {"type": "string"},
        "section_name": {"type": "string", "maxLength": 200},
        "key_findings": {
            "type": "array",
            "items": {"type": "string", "maxLength": 320},
            "maxItems": 8,
        },
        "supporting_data_points": {
            "type": "array",
            "items": {"type": "string", "maxLength": 320},
            "maxItems": 12,
        },
        "risks_or_gaps": {
            "type": "array",
            "items": {"type": "string", "maxLength": 320},
            "maxItems": 8,
        },
        "recommended_storyline": {"type": "string", "maxLength": 1500},
        "suggested_visual": {"type": ["string", "null"], "maxLength": 120},
        "suggested_controls": {
            "type": "object",
            "required": [
                "lock_key_metrics",
                "locked_metrics",
                "visual_preference",
                "include_talking_points",
                "exclude_talking_points",
            ],
            "properties": {
                "lock_key_metrics": {"type": "boolean"},
                "locked_metrics": {
                    "type": "array",
                    "items": {"type": "string", "maxLength": 160},
                    "maxItems": 12,
                },
                "visual_preference": {
                    "type": "string",
                    "enum": [v.value for v in VisualPreference],
                },
                "narrative_tone": {
                    "anyOf": [
                        {"type": "null"},
                        {"type": "string", "enum": [v.value for v in NarrativeTone]},
                    ],
                },
                "include_talking_points": {
                    "type": "array",
                    "items": {"type": "string", "maxLength": 240},
                    "maxItems": 10,
                },
                "exclude_talking_points": {
                    "type": "array",
                    "items": {"type": "string", "maxLength": 240},
                    "maxItems": 10,
                },
                "analyst_notes": {"type": ["string", "null"], "maxLength": 1500},
                "confidence": {
                    "anyOf": [
                        {"type": "null"},
                        {"type": "string", "enum": [v.value for v in AnalystConfidence]},
                    ],
                },
            },
        },
    },
}


def _sanitize_slide_text(value: Any) -> str:
    """
    Normalize and clean obvious placeholder tokens from generated slide text.

    Keeps the slide readable while avoiding raw placeholders like "null",
    "NOT PROVIDED", and "(source needed)" leaking into exported decks.
    """
    if not isinstance(value, str):
        return ""

    text = " ".join(value.replace("\u00a0", " ").split())
    if not text:
        return ""

    lowered = text.lower().strip()
    if lowered in _EMPTY_TEXT_MARKERS:
        return ""

    text = re.sub(r"\(\s*null\s*\)", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\(\s*source needed\s*\)", "(source required)", text, flags=re.IGNORECASE)
    text = _PLACEHOLDER_PATTERN.sub("data unavailable", text)
    text = re.sub(r"\bN/?A\b", "data unavailable", text, flags=re.IGNORECASE)
    text = re.sub(r"(data unavailable)(?:\s*[,;/|]\s*data unavailable)+", r"\1", text, flags=re.IGNORECASE)
    text = re.sub(r"\s{2,}", " ", text).strip(" ,;:-")

    lowered = text.lower()
    if lowered in _EMPTY_TEXT_MARKERS or lowered == "data unavailable":
        return ""

    return text


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

    def analyze_sections(
        self,
        request: DeckGenerateRequest,
        api_keys: Optional[dict[str, Optional[str]]] = None,
        openai_api_key: Optional[str] = None,
        gemini_api_key: Optional[str] = None,
    ) -> DeckSectionsAnalysisResponse:
        """
        Generate per-section analysis briefs for guided workflow.

        This step is intended to give analysts control before slide rendering.
        """
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
        logger.info(
            "Starting section analysis pass",
            extra={
                "sections": request.sections,
                "workflow_mode": request.workflow_mode.value,
            },
        )
        start_time = time.time()

        fallback_chain: list[tuple[str, str]] = []
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
            pass

        api_key = self._get_api_key(request.provider.value, api_keys)
        provider = get_provider(
            request.provider.value,
            api_key,
            request.model,
        )

        data_trust_mode = "user_auto_fetch"
        if getattr(request, "data_trust_mode", None):
            data_trust_mode = request.data_trust_mode.value

        comp_tickers = getattr(request, "comp_tickers", None)
        if not comp_tickers and getattr(request, "valuation_input", None):
            peer = request.valuation_input.peer_tickers
            if peer:
                comp_tickers = peer

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
            except Exception as exc:
                logger.warning(f"Failed to fetch comps for analysis pass: {exc}")

        dcf_data = None
        dcf_summary = None
        if getattr(request, "include_dcf", True) and data_trust_mode not in ("user_only", "narrative_only"):
            try:
                from app.deck.services.dcf_calculator import calculate_dcf

                dcf_result = calculate_dcf(ticker=request.ticker)
                if not dcf_result.get("error"):
                    dcf_data = dcf_result
                    dcf_summary = self._format_dcf_for_prompt(dcf_result)
                else:
                    logger.warning(f"DCF calculation error in analysis pass: {dcf_result.get('error')}")
            except Exception as exc:
                logger.warning(f"Failed to calculate DCF for analysis pass: {exc}")

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
        except Exception as exc:
            logger.warning(f"Failed to fetch company profile in analysis pass: {exc}")

        resolved_company_name = str(
            company_profile.get("name") or request.company_name or request.ticker
        )
        section_inputs = self._assemble_section_inputs(
            ticker=request.ticker,
            company_name=resolved_company_name,
            sector=request.sector,
            fund_constraints=request.fund_constraints.model_dump(),
            comps_summary=comps_summary,
            dcf_summary=dcf_summary,
            requested_sections=request.sections,
            company_profile=company_profile,
            request=request,
            comps_data=comps_data,
            dcf_data=dcf_data,
            comp_tickers=comp_tickers,
        )

        model_used = provider.get_model(request.model)

        from app.deck.services.llm_base import (
            AuthenticationError as LLMAuthError,
            RateLimitError as LLMRateLimitError,
            TimeoutError as LLMTimeoutError,
        )

        analyses: list[SectionAnalysisResult] = []
        errors: list[GenerationError] = []

        def analyze_section_task(section_id: str):
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
                    result = self._analyze_section(
                        provider=cur_provider,
                        section_id=section_id,
                        section_inputs=section_inputs,
                        reasoning_level=request.reasoning_level.value,
                        options_extra=cur_extra,
                    )
                    if attempt_idx > 0:
                        logger.info(
                            f"Section analysis {section_id} succeeded on fallback "
                            f"{cur_provider.PROVIDER_NAME}/{cur_model}"
                        )
                    return ("success", section_id, result)
                except (LLMAuthError, LLMRateLimitError, LLMTimeoutError) as exc:
                    last_error = exc
                    logger.warning(
                        f"Provider {cur_provider.PROVIDER_NAME} failed on analysis for "
                        f"{section_id}: {exc}. Trying next fallback..."
                    )
                    continue
                except LLMError as exc:
                    last_error = exc
                    logger.error(f"Failed section analysis for {section_id}: {exc}")
                    break
                except Exception as exc:
                    last_error = exc
                    logger.error(
                        f"Unexpected section-analysis error for {section_id}: {exc}",
                        exc_info=True,
                    )
                    break

            err = last_error or Exception("Unknown error")
            return ("error", section_id, GenerationError(
                section_id=section_id,
                error_type=type(err).__name__,
                message=str(err),
                retries_attempted=self.config.max_retries,
            ))

        if self.config.parallel_sections and len(request.sections) > 1:
            max_workers = min(self.config.max_parallel_workers, len(request.sections))
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                future_to_section = {
                    executor.submit(analyze_section_task, section_id): section_id
                    for section_id in request.sections
                }
                for future in as_completed(future_to_section):
                    status, section_id, result = future.result()
                    if status == "success":
                        analyses.append(result)
                        logger.info(f"✓ Section analysis {section_id} completed")
                    else:
                        errors.append(result)
                        logger.warning(f"✗ Section analysis {section_id} failed")
        else:
            for idx, section_id in enumerate(request.sections):
                if idx > 0 and self.config.section_delay_seconds > 0:
                    time.sleep(self.config.section_delay_seconds)
                status, section_id, result = analyze_section_task(section_id)
                if status == "success":
                    analyses.append(result)
                    logger.info(f"✓ Section analysis {section_id} completed")
                else:
                    errors.append(result)
                    logger.warning(f"✗ Section analysis {section_id} failed")

        analysis_map = {item.section_id: item for item in analyses}
        ordered_analyses = [analysis_map[s] for s in request.sections if s in analysis_map]

        total_time = time.time() - start_time
        logger.info(
            "Section analysis pass complete",
            extra={
                "total_time_ms": round(total_time * 1000, 2),
                "sections_analyzed": len(ordered_analyses),
                "errors": len(errors),
            },
        )

        return DeckSectionsAnalysisResponse(
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
            analyzed_at=datetime.utcnow().isoformat() + "Z",
            analyses=ordered_analyses,
            errors=errors,
            request_id=request_id,
        )
    
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
            inputs["workflow_mode"] = (
                request.workflow_mode.value
                if getattr(request, "workflow_mode", None)
                else WorkflowMode.AUTO.value
            )
            section_controls = getattr(request, "section_controls", None) or []
            inputs["section_controls"] = {
                control.section_id: control.model_dump(mode="json", exclude_none=True)
                for control in section_controls
            }
            section_analyses = getattr(request, "section_analyses", None) or []
            inputs["section_analyses"] = {
                analysis.section_id: analysis.model_dump(mode="json", exclude_none=True)
                for analysis in section_analyses
            }
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
        prompt = spec.build_prompt(inputs)
        guided_appendix = self._build_guided_appendix(section_id, inputs)
        if guided_appendix:
            prompt = f"{prompt}\n\n{guided_appendix}"
        return prompt, spec.schema, True

    def _build_guided_appendix(
        self,
        section_id: str,
        inputs: dict[str, Any],
    ) -> str:
        """
        Build a guided-mode appendix from analyst-approved section controls.
        """
        controls_map = inputs.get("section_controls") or {}
        analyses_map = inputs.get("section_analyses") or {}
        control = controls_map.get(section_id) if isinstance(controls_map, dict) else None
        analysis = analyses_map.get(section_id) if isinstance(analyses_map, dict) else None

        if not control and not analysis:
            return ""
        if control and not bool(control.get("approved", True)):
            return ""

        lines = [
            "## ANALYST GUIDANCE (HIGHEST PRIORITY)",
            "Follow this approved guidance while still satisfying the JSON schema.",
        ]

        if analysis:
            key_findings = self._normalize_text_list(analysis.get("key_findings"))
            supporting_points = self._normalize_text_list(analysis.get("supporting_data_points"))
            risks_or_gaps = self._normalize_text_list(analysis.get("risks_or_gaps"))
            storyline = str(analysis.get("recommended_storyline") or "").strip()
            suggested_visual = str(analysis.get("suggested_visual") or "").strip()

            if key_findings:
                lines.append("Approved key findings:")
                lines.extend(f"- {item}" for item in key_findings[:8])
            if supporting_points:
                lines.append("Supporting data points to reference:")
                lines.extend(f"- {item}" for item in supporting_points[:12])
            if risks_or_gaps:
                lines.append("Known risks / evidence gaps:")
                lines.extend(f"- {item}" for item in risks_or_gaps[:8])
            if storyline:
                lines.append(f"Preferred storyline: {storyline}")
            if suggested_visual:
                lines.append(f"Preferred visual direction: {suggested_visual}")

        if control:
            visual_pref = str(control.get("visual_preference") or "auto").strip()
            narrative_tone = str(control.get("narrative_tone") or "").strip()
            lock_metrics = bool(control.get("lock_key_metrics", False))
            locked_metrics = self._normalize_text_list(control.get("locked_metrics"))
            include_points = self._normalize_text_list(control.get("include_talking_points"))
            exclude_points = self._normalize_text_list(control.get("exclude_talking_points"))
            analyst_notes = str(control.get("analyst_notes") or "").strip()
            confidence = str(control.get("confidence") or "").strip()

            if visual_pref and visual_pref != "auto":
                lines.append(
                    f"Set layout_hints.suggested_visual to align with '{visual_pref}' when possible."
                )
            if narrative_tone:
                lines.append(f"Narrative tone: {narrative_tone}.")
            if lock_metrics and locked_metrics:
                lines.append(
                    "Do not alter, substitute, or omit these locked metrics/statements:"
                )
                lines.extend(f"- {item}" for item in locked_metrics[:12])
            if include_points:
                lines.append("Required talking points:")
                lines.extend(f"- {item}" for item in include_points[:10])
            if exclude_points:
                lines.append("Avoid these talking points:")
                lines.extend(f"- {item}" for item in exclude_points[:10])
            if analyst_notes:
                lines.append(f"Analyst notes: {analyst_notes}")
            if confidence:
                lines.append(
                    f"Analyst confidence marker: {confidence}. Reflect uncertainty transparently in wording."
                )

        return "\n".join(lines)

    def _normalize_text_list(self, value: Any) -> list[str]:
        """Normalize unknown values into a clean list of strings."""
        if not isinstance(value, list):
            return []
        cleaned: list[str] = []
        for item in value:
            text = _sanitize_slide_text(item)
            if text:
                cleaned.append(text)
        return cleaned

    def _build_section_analysis_prompt(
        self,
        section_id: str,
        section_inputs: dict[str, Any],
    ) -> str:
        """Build the prompt for pre-slide section analysis."""
        section_meta = get_section_metadata(section_id)
        section_label = section_meta.get("label", section_id.replace("_", " ").title())
        section_description = section_meta.get("description", "")

        summary_payload = {
            "company": {
                "ticker": section_inputs.get("ticker"),
                "name": section_inputs.get("company_name"),
                "sector": section_inputs.get("sector"),
                "industry": section_inputs.get("industry"),
                "description": section_inputs.get("description"),
            },
            "fund_constraints": section_inputs.get("fund_constraints"),
            "position": section_inputs.get("position"),
            "deck_length": section_inputs.get("deck_length"),
            "data_trust_mode": section_inputs.get("data_trust_mode"),
            "thesis": section_inputs.get("thesis"),
            "catalysts": section_inputs.get("catalysts"),
            "valuation": section_inputs.get("valuation"),
            "risks": section_inputs.get("risks"),
            "data_blocks": section_inputs.get("data_blocks"),
            "user_constraints": section_inputs.get("user_constraints"),
            "comps_summary": section_inputs.get("comps_summary"),
            "dcf_summary": section_inputs.get("dcf_summary"),
        }

        import json

        payload_json = json.dumps(summary_payload, ensure_ascii=True, indent=2)

        return (
            f"Prepare an analyst briefing for section '{section_id}' ({section_label}).\n"
            f"Section purpose: {section_description}\n\n"
            "Use the context below to propose a concise pre-slide analysis. "
            "Do not invent citations. Mark uncertainty where evidence is weak.\n\n"
            "Return JSON only with:\n"
            "- key_findings: the most decision-relevant findings\n"
            "- supporting_data_points: facts/metrics to validate or anchor narrative\n"
            "- risks_or_gaps: what could break confidence or needs analyst review\n"
            "- recommended_storyline: best narrative arc for the eventual slide(s)\n"
            "- suggested_visual: optional visual suggestion\n"
            "- suggested_controls: practical defaults the analyst can edit\n\n"
            "Context JSON:\n"
            f"{payload_json}"
        )

    def _transform_section_analysis_response(
        self,
        content: dict[str, Any],
        section_id: str,
    ) -> SectionAnalysisResult:
        """Transform raw LLM analysis into a typed section analysis result."""
        section_meta = get_section_metadata(section_id)
        section_name = section_meta.get("label", section_id.replace("_", " ").title())
        suggested_controls = content.get("suggested_controls") or {}
        visual_raw = str(suggested_controls.get("visual_preference") or VisualPreference.AUTO.value)
        tone_raw = suggested_controls.get("narrative_tone")
        confidence_raw = suggested_controls.get("confidence")

        try:
            visual_preference = VisualPreference(visual_raw)
        except ValueError:
            visual_preference = VisualPreference.AUTO

        try:
            narrative_tone = NarrativeTone(str(tone_raw)) if tone_raw else None
        except ValueError:
            narrative_tone = None

        try:
            confidence = AnalystConfidence(str(confidence_raw)) if confidence_raw else None
        except ValueError:
            confidence = None

        return SectionAnalysisResult(
            section_id=section_id,
            section_name=section_name,
            key_findings=self._normalize_text_list(content.get("key_findings")),
            supporting_data_points=self._normalize_text_list(content.get("supporting_data_points")),
            risks_or_gaps=self._normalize_text_list(content.get("risks_or_gaps")),
            recommended_storyline=_sanitize_slide_text(content.get("recommended_storyline"))[:1500],
            suggested_visual=_sanitize_slide_text(content.get("suggested_visual"))[:120] or None,
            suggested_controls=SectionAnalysisControls(
                lock_key_metrics=bool(suggested_controls.get("lock_key_metrics", False)),
                locked_metrics=self._normalize_text_list(suggested_controls.get("locked_metrics"))[:12],
                visual_preference=visual_preference,
                narrative_tone=narrative_tone,
                include_talking_points=self._normalize_text_list(
                    suggested_controls.get("include_talking_points")
                )[:10],
                exclude_talking_points=self._normalize_text_list(
                    suggested_controls.get("exclude_talking_points")
                )[:10],
                analyst_notes=(
                    _sanitize_slide_text(suggested_controls.get("analyst_notes"))[:1500]
                    or None
                ),
                confidence=confidence,
            ),
        )

    def _analyze_section(
        self,
        provider: LLMProvider,
        section_id: str,
        section_inputs: dict[str, Any],
        reasoning_level: str,
        options_extra: Optional[dict[str, Any]] = None,
    ) -> SectionAnalysisResult:
        """Generate analysis brief for a single section."""
        options = LLMOptions(
            reasoning_level=reasoning_level,
            timeout=self.config.timeout,
            extra=options_extra or {},
        )
        prompt = self._build_section_analysis_prompt(section_id, section_inputs)

        response = provider.generate_with_retry(
            system_prompt=SYSTEM_PROMPT,
            user_prompt=prompt,
            json_schema=SECTION_ANALYSIS_JSON_SCHEMA,
            options=options,
            max_retries=self.config.max_retries,
            fix_prompt_builder=get_fix_prompt,
        )
        result = self._transform_section_analysis_response(response.content, section_id)
        result.generation_metadata = {
            "model": response.model,
            "latency_ms": response.latency_ms,
            "retries": response.retries,
            "tokens": response.usage,
        }
        return result
    
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
                    bullet_dict = {"text": bullet, "source_needed": False}
                elif isinstance(bullet, dict):
                    bullet_dict = bullet
                else:
                    continue

                cleaned_text = _sanitize_slide_text(bullet_dict.get("text"))
                if not cleaned_text:
                    continue

                normalized_bullets.append({
                    "text": cleaned_text,
                    "source_needed": bool(bullet_dict.get("source_needed", False)),
                })
            
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
            
            speaker_notes = "\n".join(
                line
                for raw_line in str(slide_data.get("speaker_notes", "")).splitlines()
                if (line := _sanitize_slide_text(raw_line))
            )

            cleaned_title = _sanitize_slide_text(slide_data.get("title", ""))
            if not cleaned_title:
                cleaned_title = section_id.replace("_", " ").title()

            slides.append(Slide(
                slide_id=slide_data.get("slide_id", f"{section_id}_{len(slides) + 1}"),
                title=cleaned_title,
                bullets=bullets[:4],  # Enforce max 4
                speaker_notes=speaker_notes,
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
