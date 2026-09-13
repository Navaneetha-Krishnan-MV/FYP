import json
from types import SimpleNamespace

from app.config import settings
from app.llm.gemini_client import GeminiClient


class FakeModels:
    def __init__(self, payloads):
        self.payloads = iter(payloads)
        self.calls = []

    def generate_content(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(text=json.dumps(next(self.payloads)))


def install_fake_client(monkeypatch, payloads):
    models = FakeModels(payloads)
    client = SimpleNamespace(models=models)
    monkeypatch.setattr(
        GeminiClient,
        "get_client",
        classmethod(lambda cls: client),
    )
    return models


def test_query_expansion_reaches_configured_gemini_model(monkeypatch):
    expected = {
        "expanded_query": "session expiry invalidation",
        "search_terms": ["session", "expiry", "invalidate"],
        "concepts": ["authentication"],
    }
    models = install_fake_client(monkeypatch, [expected])

    result = GeminiClient.generate_query_expansion(
        "Session remains active",
        "Expired sessions are not invalidated",
    )

    assert result == expected
    assert models.calls[0]["model"] == settings.GEMINI_MODEL_NAME


def test_root_cause_analysis_reaches_configured_gemini_model(monkeypatch):
    expected = {
        "root_cause_file": "src/session.py",
        "root_cause_function": "invalidate_session",
        "root_cause_commit": "abc123",
        "explanation": "The expiry branch skips invalidation.",
        "suggested_fix": "Invalidate the session in the expiry branch.",
        "confidence": "HIGH",
        "dependency_path_summary": "request -> session -> expiry",
    }
    models = install_fake_client(monkeypatch, [expected])

    result = GeminiClient.generate_root_cause_analysis(
        "Session remains active",
        "Expired sessions are not invalidated",
        {},
    )

    assert result == expected
    assert models.calls[0]["model"] == settings.GEMINI_MODEL_NAME
