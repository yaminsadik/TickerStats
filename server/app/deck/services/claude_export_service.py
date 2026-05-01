"""Claude Skills-powered PPTX/PDF export for generated deck JSON."""

from __future__ import annotations

import hashlib
import json
import re
import time
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx

from app.deck.api.schemas import ClaudeExportFormat
from app.deck.utils.logging import get_logger

logger = get_logger(__name__)


ANTHROPIC_MESSAGES_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_FILES_URL = "https://api.anthropic.com/v1/files"
SKILLS_BETA_HEADER = "code-execution-2025-08-25,skills-2025-10-02,files-api-2025-04-14"
FILES_BETA_HEADER = "files-api-2025-04-14"
PROMPT_VERSION = "claude-export-v2"


class ClaudeExportError(Exception):
    """Raised when Claude Skills export fails."""


@dataclass(frozen=True)
class ClaudeExportResult:
    content: bytes
    filename: str
    media_type: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    latency_ms: int = 0
    cached: bool = False
    source_file_ids: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class _DownloadedFile:
    file_id: str
    filename: str
    content: bytes


class ClaudeDeckExportService:
    """Generate high-quality deck documents from canonical deck JSON."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        cache_dir: str,
        max_slides: int,
        timeout_seconds: float = 180.0,
    ) -> None:
        if not api_key:
            raise ClaudeExportError("ANTHROPIC_API_KEY is required for Claude export")
        self.api_key = api_key
        self.model = model
        self.cache_dir = Path(cache_dir)
        self.max_slides = max_slides
        self.timeout_seconds = timeout_seconds
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def export(
        self,
        *,
        deck: dict[str, Any],
        export_format: ClaudeExportFormat,
        title: str | None = None,
    ) -> ClaudeExportResult:
        slide_count = self._count_slides(deck)
        if slide_count <= 0:
            raise ClaudeExportError("Deck must contain at least one slide")
        if slide_count > self.max_slides:
            raise ClaudeExportError(
                f"Deck has {slide_count} slides; Claude export is capped at {self.max_slides}"
            )

        safe_title = self._safe_filename(title or self._infer_title(deck))
        cache_key = self._cache_key(deck=deck, export_format=export_format, title=safe_title)
        cache_path = self.cache_dir / f"{cache_key}.{self._cache_extension(export_format)}"
        meta_path = self.cache_dir / f"{cache_key}.json"

        if cache_path.exists():
            return ClaudeExportResult(
                content=cache_path.read_bytes(),
                filename=self._result_filename(safe_title, export_format),
                media_type=self._media_type(export_format),
                model=self.model,
                cached=True,
            )

        started = time.monotonic()
        message = self._create_message(deck=deck, export_format=export_format, title=safe_title)
        usage = message.get("usage") or {}
        file_ids = list(dict.fromkeys(self._extract_file_ids(message)))
        if not file_ids:
            raise ClaudeExportError("Claude export completed without returning a file")

        downloaded = [self._download_file(file_id) for file_id in file_ids]
        selected = self._select_files(downloaded, export_format)
        content = self._build_content(selected, export_format)
        cache_path.write_bytes(content)

        latency_ms = int((time.monotonic() - started) * 1000)
        meta_path.write_text(
            json.dumps(
                {
                    "model": self.model,
                    "format": export_format.value,
                    "title": safe_title,
                    "file_ids": [item.file_id for item in selected],
                    "latency_ms": latency_ms,
                    "usage": usage,
                },
                indent=2,
                sort_keys=True,
            )
        )

        return ClaudeExportResult(
            content=content,
            filename=self._result_filename(safe_title, export_format),
            media_type=self._media_type(export_format),
            model=self.model,
            input_tokens=int(usage.get("input_tokens") or 0),
            output_tokens=int(usage.get("output_tokens") or 0),
            latency_ms=latency_ms,
            cached=False,
            source_file_ids=[item.file_id for item in selected],
        )

    def _create_message(
        self,
        *,
        deck: dict[str, Any],
        export_format: ClaudeExportFormat,
        title: str,
    ) -> dict[str, Any]:
        skills = self._skills_for_format(export_format)
        prompt = self._build_prompt(deck=deck, export_format=export_format, title=title)
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "anthropic-beta": SKILLS_BETA_HEADER,
            "content-type": "application/json",
        }
        payload = {
            "model": self.model,
            "max_tokens": 4096,
            "container": {"skills": skills},
            "messages": [{"role": "user", "content": prompt}],
            "tools": [{"type": "code_execution_20250825", "name": "code_execution"}],
        }

        try:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                response = client.post(ANTHROPIC_MESSAGES_URL, headers=headers, json=payload)
                response.raise_for_status()
                return response.json()
        except httpx.HTTPStatusError as exc:
            detail = exc.response.text[:500]
            logger.warning("Claude export API error: %s", detail)
            raise ClaudeExportError(f"Claude export API error: {exc.response.status_code}") from exc
        except httpx.HTTPError as exc:
            raise ClaudeExportError(f"Claude export request failed: {exc}") from exc

    def _download_file(self, file_id: str) -> _DownloadedFile:
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "anthropic-beta": FILES_BETA_HEADER,
        }
        try:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                metadata_response = client.get(f"{ANTHROPIC_FILES_URL}/{file_id}", headers=headers)
                metadata_response.raise_for_status()
                metadata = metadata_response.json()
                filename = self._safe_filename(str(metadata.get("filename") or f"{file_id}.bin"))

                content_response = client.get(f"{ANTHROPIC_FILES_URL}/{file_id}/content", headers=headers)
                content_response.raise_for_status()
                return _DownloadedFile(file_id=file_id, filename=filename, content=content_response.content)
        except httpx.HTTPStatusError as exc:
            raise ClaudeExportError(f"Claude file download failed: {exc.response.status_code}") from exc
        except httpx.HTTPError as exc:
            raise ClaudeExportError(f"Claude file download failed: {exc}") from exc

    def _build_prompt(
        self,
        *,
        deck: dict[str, Any],
        export_format: ClaudeExportFormat,
        title: str,
    ) -> str:
        normalized = json.dumps(deck, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
        requested = "PowerPoint and PDF" if export_format == ClaudeExportFormat.BOTH else export_format.value.upper()
        return (
            f"Create a polished institutional investment pitch deck export titled \"{title}\".\n"
            f"Requested output: {requested}.\n\n"
            "Use the provided deck JSON as the source of truth. Preserve every fact, number, ticker, "
            "company name, bullet meaning, and speaker note. Do not add new financial claims or rewrite "
            "the investment thesis beyond light copy fitting.\n\n"
            "Do a full document redesign rather than a light restyle. Do not mirror a generic JSON/card layout. "
            "Create an institutional presentation with a distinctive cover, strong section headers, varied slide "
            "layouts, executive-summary callouts, KPI tiles, comparison tables, timelines, SWOT grids, and chart-like "
            "visual treatments where the source content supports them. Use the JSON only as content input, not as a "
            "layout template.\n\n"
            "Design direction: modern investment committee style, crisp typography, clean navy/white/slate palette "
            "with one accent color, strong visual hierarchy, generous spacing, readable tables/cards, and no decorative "
            "clutter. If the deck JSON includes generation errors or only a subset of requested sections, include a "
            "short status note in the appendix that makes clear which sections were not available in the source JSON.\n\n"
            "Return the generated file through the enabled Skill/code execution environment.\n\n"
            f"Deck JSON:\n{normalized}"
        )

    def _select_files(
        self,
        files: list[_DownloadedFile],
        export_format: ClaudeExportFormat,
    ) -> list[_DownloadedFile]:
        expected_suffixes = {
            ClaudeExportFormat.PPTX: [".pptx"],
            ClaudeExportFormat.PDF: [".pdf"],
            ClaudeExportFormat.BOTH: [".pptx", ".pdf"],
        }[export_format]

        selected: list[_DownloadedFile] = []
        for suffix in expected_suffixes:
            match = next((item for item in files if item.filename.lower().endswith(suffix)), None)
            if match is None and export_format != ClaudeExportFormat.BOTH and len(files) == 1:
                match = files[0]
            if match is None:
                raise ClaudeExportError(f"Claude did not return a {suffix} file")
            selected.append(match)
        return selected

    def _build_content(
        self,
        files: list[_DownloadedFile],
        export_format: ClaudeExportFormat,
    ) -> bytes:
        if export_format != ClaudeExportFormat.BOTH:
            return files[0].content

        import io

        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for item in files:
                archive.writestr(item.filename, item.content)
        return buffer.getvalue()

    def _extract_file_ids(self, value: Any) -> list[str]:
        ids: list[str] = []
        if isinstance(value, dict):
            file_id = value.get("file_id")
            if isinstance(file_id, str):
                ids.append(file_id)
            for child in value.values():
                ids.extend(self._extract_file_ids(child))
        elif isinstance(value, list):
            for child in value:
                ids.extend(self._extract_file_ids(child))
        return ids

    def _skills_for_format(self, export_format: ClaudeExportFormat) -> list[dict[str, str]]:
        skill_ids = ["pptx", "pdf"] if export_format == ClaudeExportFormat.BOTH else [export_format.value]
        return [{"type": "anthropic", "skill_id": skill_id, "version": "latest"} for skill_id in skill_ids]

    def _cache_key(
        self,
        *,
        deck: dict[str, Any],
        export_format: ClaudeExportFormat,
        title: str,
    ) -> str:
        payload = {
            "deck": deck,
            "format": export_format.value,
            "model": self.model,
            "prompt_version": PROMPT_VERSION,
            "title": title,
        }
        encoded = json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode()
        return hashlib.sha256(encoded).hexdigest()

    def _count_slides(self, deck: dict[str, Any]) -> int:
        sections = deck.get("results") or deck.get("sections") or []
        if not isinstance(sections, list):
            return 0
        return sum(len(section.get("slides") or []) for section in sections if isinstance(section, dict))

    def _infer_title(self, deck: dict[str, Any]) -> str:
        metadata = deck.get("metadata") if isinstance(deck.get("metadata"), dict) else {}
        ticker = str(deck.get("ticker") or metadata.get("ticker") or "deck")
        company = str(deck.get("company_name") or metadata.get("company_name") or ticker)
        return f"{company} {ticker} pitch deck".strip()

    def _result_filename(self, title: str, export_format: ClaudeExportFormat) -> str:
        return f"{title}.{self._cache_extension(export_format)}"

    def _cache_extension(self, export_format: ClaudeExportFormat) -> str:
        return "zip" if export_format == ClaudeExportFormat.BOTH else export_format.value

    def _media_type(self, export_format: ClaudeExportFormat) -> str:
        if export_format == ClaudeExportFormat.PPTX:
            return "application/vnd.openxmlformats-officedocument.presentationml.presentation"
        if export_format == ClaudeExportFormat.PDF:
            return "application/pdf"
        return "application/zip"

    def _safe_filename(self, value: str) -> str:
        cleaned = re.sub(r"[^A-Za-z0-9._ -]+", "", value).strip().replace(" ", "_")
        return cleaned[:120] or "deck"
