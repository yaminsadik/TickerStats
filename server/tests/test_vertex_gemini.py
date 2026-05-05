import json
import sys
import types
from types import SimpleNamespace

import pytest

from app.core.config import settings
from app.deck.api.routes_deck import VERTEX_GEMINI_KEY_SENTINEL, get_api_keys
from app.deck.services.llm_gemini import GeminiProvider, VERTEX_CLOUD_PLATFORM_SCOPE
from app.deck.services.llm_base import LLMOptions
from app.deck.services.llm_base import AuthenticationError
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


def _install_fake_google_genai(monkeypatch, client_factory):
    fake_google = types.ModuleType("google")
    fake_genai = SimpleNamespace(Client=client_factory)
    fake_google.genai = fake_genai

    monkeypatch.setitem(sys.modules, "google", fake_google)
    monkeypatch.setitem(sys.modules, "google.genai", fake_genai)


def _install_fake_google_service_account(monkeypatch, credentials_factory):
    class _FakeCredentials:
        from_service_account_info = staticmethod(credentials_factory)

    fake_service_account = SimpleNamespace(Credentials=_FakeCredentials)
    fake_oauth2 = types.ModuleType("google.oauth2")
    fake_oauth2.service_account = fake_service_account

    fake_google = sys.modules.get("google")
    if fake_google is not None:
        fake_google.oauth2 = fake_oauth2

    monkeypatch.setitem(sys.modules, "google.oauth2", fake_oauth2)
    monkeypatch.setitem(sys.modules, "google.oauth2.service_account", fake_service_account)


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


def test_vertex_client_uses_service_account_json_env(monkeypatch):
    captured = {}
    fake_credentials = object()

    def client_factory(**kwargs):
        captured["client_kwargs"] = kwargs
        return _FakeClient()

    def credentials_factory(info, scopes=None):
        captured["credentials_info"] = info
        captured["credentials_scopes"] = scopes
        return fake_credentials

    _install_fake_google_genai(monkeypatch, client_factory)
    _install_fake_google_service_account(monkeypatch, credentials_factory)

    monkeypatch.setattr(settings, "GOOGLE_GENAI_USE_VERTEXAI", True)
    monkeypatch.setattr(settings, "GOOGLE_CLOUD_PROJECT", "tickerstats-test")
    monkeypatch.setattr(settings, "GOOGLE_CLOUD_LOCATION", "us-central1")
    monkeypatch.setattr(settings, "GOOGLE_APPLICATION_CREDENTIALS", "/missing/file.json")
    monkeypatch.setattr(
        settings,
        "GOOGLE_APPLICATION_CREDENTIALS_JSON",
        json.dumps(
            {
                "type": "service_account",
                "project_id": "tickerstats-test",
                "private_key_id": "test-key-id",
                "private_key": "redacted",
                "client_email": "svc@example.iam.gserviceaccount.com",
                "token_uri": "https://oauth2.googleapis.com/token",
            }
        ),
    )
    monkeypatch.setattr(settings, "GOOGLE_APPLICATION_CREDENTIALS_JSON_BASE64", "")

    provider = GeminiProvider(api_key="", default_model="gemini-3.1-pro-preview")
    client = provider._get_client()

    assert isinstance(client, _FakeClient)
    assert captured["credentials_info"]["type"] == "service_account"
    assert captured["credentials_scopes"] == [VERTEX_CLOUD_PLATFORM_SCOPE]
    assert captured["client_kwargs"]["credentials"] is fake_credentials
    assert captured["client_kwargs"]["project"] == "tickerstats-test"
    assert captured["client_kwargs"]["location"] == "us-central1"


def test_vertex_client_reports_missing_credentials_file(monkeypatch):
    def client_factory(**kwargs):
        raise AssertionError("Client should not be created with a missing ADC file")

    _install_fake_google_genai(monkeypatch, client_factory)

    monkeypatch.setattr(settings, "GOOGLE_GENAI_USE_VERTEXAI", True)
    monkeypatch.setattr(settings, "GOOGLE_CLOUD_PROJECT", "tickerstats-test")
    monkeypatch.setattr(settings, "GOOGLE_CLOUD_LOCATION", "us-central1")
    monkeypatch.setattr(settings, "GOOGLE_APPLICATION_CREDENTIALS", "/missing/file.json")
    monkeypatch.setattr(settings, "GOOGLE_APPLICATION_CREDENTIALS_JSON", "")
    monkeypatch.setattr(settings, "GOOGLE_APPLICATION_CREDENTIALS_JSON_BASE64", "")

    provider = GeminiProvider(api_key="", default_model="gemini-3.1-pro-preview")

    try:
        provider._get_client()
    except AuthenticationError as exc:
        message = str(exc)
    else:
        raise AssertionError("Expected AuthenticationError")

    assert "GOOGLE_APPLICATION_CREDENTIALS points to" in message
    assert "GOOGLE_APPLICATION_CREDENTIALS_JSON_BASE64" in message


def test_vertex_model_lookup_error_includes_global_location_hint(monkeypatch):
    class _FailingModels:
        def generate_content(self, **kwargs):
            raise RuntimeError(
                "404 NOT_FOUND. {'error': {'code': 404, 'message': "
                "'Publisher Model `projects/test/locations/us-central1/publishers/google/models/gemini-3.1-pro-preview` "
                "was not found or your project does not have access to it.'}}"
            )

    class _FailingClient:
        def __init__(self):
            self.models = _FailingModels()

    monkeypatch.setattr(settings, "GOOGLE_CLOUD_LOCATION", "us-central1")

    provider = GeminiProvider(api_key="", default_model="gemini-3.1-pro-preview")
    monkeypatch.setattr(provider, "_get_client", lambda: _FailingClient())
    monkeypatch.setattr(provider, "_use_vertex", lambda: True)

    with pytest.raises(AuthenticationError) as exc:
        provider.generate_json(
            system_prompt="Return JSON.",
            user_prompt="Say ok.",
            json_schema={
                "type": "object",
                "properties": {"status": {"type": "string"}},
                "required": ["status"],
            },
            options=LLMOptions(reasoning_level="low", extra={"model": "gemini-3.1-pro-preview"}),
        )

    assert "GOOGLE_CLOUD_LOCATION=global" in str(exc.value)
