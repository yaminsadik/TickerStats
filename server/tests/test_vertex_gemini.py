from types import SimpleNamespace

from app.core.config import settings
from app.deck.api.routes_deck import VERTEX_GEMINI_KEY_SENTINEL, get_api_keys
from app.deck.services.llm_gemini import GeminiProvider
from app.deck.services.llm_base import LLMOptions
from app.deck.services.model_policy import resolve_model


class _FakeModels:
    def __init__(self):
        self.last_call = None

    def generate_content(self, **kwargs):
        self.last_call = kwargs
        return SimpleNamespace(
            candidates=[SimpleNamespace(finish_reason="STOP")],
            text='{"status":"ok"}',
            usage_metadata=SimpleNamespace(
                prompt_token_count=11,
                candidates_token_count=3,
                total_token_count=14,
            ),
        )


class _FakeClient:
    def __init__(self):
        self.models = _FakeModels()


def test_gemini_provider_uses_genai_structured_json(monkeypatch):
    fake_client = _FakeClient()
    provider = GeminiProvider(api_key="", default_model="gemini-3.1-pro-preview")
    monkeypatch.setattr(provider, "_get_client", lambda: fake_client)
    monkeypatch.setattr(provider, "_use_vertex", lambda: True)

    response = provider.generate_json(
        system_prompt="Return JSON.",
        user_prompt="Say ok.",
        json_schema={
            "type": "object",
            "properties": {"status": {"type": "string"}},
            "required": ["status"],
        },
        options=LLMOptions(reasoning_level="low", extra={"model": "gemini-3.1-pro-preview"}),
    )

    assert response.content == {"status": "ok"}
    assert response.model == "gemini-3.1-pro-preview"
    assert response.provider == "gemini"
    assert response.usage["total_tokens"] == 14
    assert fake_client.models.last_call["model"] == "gemini-3.1-pro-preview"
    assert fake_client.models.last_call["config"]["response_mime_type"] == "application/json"
    assert "response_json_schema" in fake_client.models.last_call["config"]


def test_vertex_mode_marks_gemini_available_without_api_key(monkeypatch):
    monkeypatch.setattr(settings, "GOOGLE_GENAI_USE_VERTEXAI", True)
    monkeypatch.setattr(settings, "GOOGLE_CLOUD_PROJECT", "tickerstats-test")
    monkeypatch.setattr(settings, "GOOGLE_CLOUD_LOCATION", "us-central1")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)

    request = SimpleNamespace(headers={})
    api_keys = get_api_keys(request)

    assert api_keys["gemini"] == VERTEX_GEMINI_KEY_SENTINEL

    decision = resolve_model(
        plan_tier="free",
        analysis_depth="medium",
        model_mode="auto",
        requested_model_id=None,
        thinking_requested=False,
        available_keys=api_keys,
    )

    assert decision.provider == "gemini"
    assert decision.model == "gemini-3.1-pro-preview"
