from types import SimpleNamespace

import pytest
from google.genai.errors import ClientError

from app.config import settings
from app.indexing import embedder
from app.indexing.embedder import CodeEmbedder, EmbeddingError
from app.llm.gemini_client import GeminiClient


class FakeModels:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.calls = []

    def embed_content(self, **kwargs):
        self.calls.append(kwargs)
        response = next(self.responses)
        if isinstance(response, Exception):
            raise response
        return response


def embedding_response(vectors):
    return SimpleNamespace(
        embeddings=[SimpleNamespace(values=vector) for vector in vectors]
    )


def install_fake_client(monkeypatch, responses):
    models = FakeModels(responses)
    client = SimpleNamespace(models=models)
    monkeypatch.setattr(
        GeminiClient,
        "get_client",
        classmethod(lambda cls: client),
    )
    monkeypatch.setattr(
        embedder._EmbeddingRequestPacer,
        "wait",
        classmethod(lambda cls: None),
    )
    return models


def test_embed_batch_groups_multiple_texts_into_each_api_request(monkeypatch):
    monkeypatch.setattr(settings, "EMBEDDING_DIMENSION", 3)
    models = install_fake_client(
        monkeypatch,
        [
            embedding_response([[1, 2, 3], [4, 5, 6]]),
            embedding_response([[7, 8, 9]]),
        ],
    )

    vectors = CodeEmbedder.embed_batch(["one", "two", "three"], batch_size=2)

    assert vectors == [[1, 2, 3], [4, 5, 6], [7, 8, 9]]
    assert [call["contents"] for call in models.calls] == [
        ["one", "two"],
        ["three"],
    ]


def test_embed_batch_retries_429_with_exponential_backoff(monkeypatch):
    monkeypatch.setattr(settings, "EMBEDDING_DIMENSION", 3)
    monkeypatch.setattr(settings, "EMBEDDING_RETRY_BASE_SECONDS", 2.0)
    monkeypatch.setattr(settings, "EMBEDDING_RETRY_MAX_SECONDS", 60.0)
    rate_limit_error = ClientError(
        429,
        {"error": {"status": "RESOURCE_EXHAUSTED", "message": "quota"}},
    )
    models = install_fake_client(
        monkeypatch,
        [rate_limit_error, embedding_response([[1, 2, 3]])],
    )
    sleeps = []
    monkeypatch.setattr(embedder.random, "uniform", lambda start, end: 0)
    monkeypatch.setattr(embedder.time, "sleep", sleeps.append)

    assert CodeEmbedder.embed_batch(["one"]) == [[1, 2, 3]]
    assert len(models.calls) == 2
    assert sleeps == [2.0]


def test_embed_batch_does_not_retry_non_transient_client_error(monkeypatch):
    monkeypatch.setattr(settings, "EMBEDDING_DIMENSION", 3)
    bad_request = ClientError(
        400,
        {"error": {"status": "INVALID_ARGUMENT", "message": "bad input"}},
    )
    models = install_fake_client(monkeypatch, [bad_request])

    with pytest.raises(EmbeddingError, match=r"after 1 attempt"):
        CodeEmbedder.embed_batch(["one"])

    assert len(models.calls) == 1


def test_embed_batch_rejects_missing_response_vectors(monkeypatch):
    monkeypatch.setattr(settings, "EMBEDDING_DIMENSION", 3)
    install_fake_client(monkeypatch, [embedding_response([])])

    with pytest.raises(EmbeddingError, match="returned no embeddings"):
        CodeEmbedder.embed_batch(["one"])
