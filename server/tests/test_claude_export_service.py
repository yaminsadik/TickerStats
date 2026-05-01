import pytest
from pydantic import ValidationError

from app.deck.api.schemas import ClaudeExportFormat, DeckClaudeExportRequest
from app.deck.services.claude_export_service import (
    ClaudeDeckExportService,
    ClaudeExportError,
    _DownloadedFile,
)


def _sample_deck():
    return {
        "ticker": "ACN",
        "company_name": "Accenture",
        "generated_at": "2026-01-01T00:00:00Z",
        "provider_used": {
            "provider": "gemini",
            "model": "gemini-3-flash-preview",
            "reasoning_level": "medium",
        },
        "results": [
            {
                "section_id": "overview",
                "section_name": "Overview",
                "slides": [
                    {
                        "slide_id": "overview_1",
                        "title": "Accenture Overview",
                        "bullets": [
                            {"text": "Global professional services company", "source_needed": False},
                        ],
                        "speaker_notes": "Introduce the company.",
                    },
                ],
            },
        ],
    }


def test_claude_export_request_requires_slides():
    with pytest.raises(ValidationError):
        DeckClaudeExportRequest(deck={"results": []}, export_format=ClaudeExportFormat.PPTX)


def test_claude_export_service_uses_cache(tmp_path, monkeypatch):
    service = ClaudeDeckExportService(
        api_key="test-key",
        model="claude-sonnet-4-5",
        cache_dir=str(tmp_path),
        max_slides=10,
    )
    calls = {"create": 0}

    def fake_create_message(**_kwargs):
        calls["create"] += 1
        return {
            "usage": {"input_tokens": 100, "output_tokens": 50},
            "content": [{"file_id": "file_123"}],
        }

    def fake_download_file(file_id):
        return _DownloadedFile(
            file_id=file_id,
            filename="ACN_pitch_deck.pptx",
            content=b"pptx-bytes",
        )

    monkeypatch.setattr(service, "_create_message", fake_create_message)
    monkeypatch.setattr(service, "_download_file", fake_download_file)

    first = service.export(
        deck=_sample_deck(),
        export_format=ClaudeExportFormat.PPTX,
        title="ACN pitch deck",
    )
    second = service.export(
        deck=_sample_deck(),
        export_format=ClaudeExportFormat.PPTX,
        title="ACN pitch deck",
    )

    assert first.content == b"pptx-bytes"
    assert first.cached is False
    assert second.content == b"pptx-bytes"
    assert second.cached is True
    assert calls["create"] == 1


def test_claude_export_service_surfaces_api_errors(tmp_path, monkeypatch):
    service = ClaudeDeckExportService(
        api_key="test-key",
        model="claude-sonnet-4-5",
        cache_dir=str(tmp_path),
        max_slides=10,
    )

    def fake_create_message(**_kwargs):
        raise ClaudeExportError("Claude export API error: 500")

    monkeypatch.setattr(service, "_create_message", fake_create_message)

    with pytest.raises(ClaudeExportError, match="API error"):
        service.export(
            deck=_sample_deck(),
            export_format=ClaudeExportFormat.PDF,
            title="ACN pitch deck",
        )


def test_claude_export_service_enforces_slide_cap(tmp_path):
    service = ClaudeDeckExportService(
        api_key="test-key",
        model="claude-sonnet-4-5",
        cache_dir=str(tmp_path),
        max_slides=0,
    )

    with pytest.raises(ClaudeExportError, match="capped"):
        service.export(
            deck=_sample_deck(),
            export_format=ClaudeExportFormat.PPTX,
            title="ACN pitch deck",
        )
