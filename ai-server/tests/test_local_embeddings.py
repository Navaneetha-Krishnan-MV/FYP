from types import SimpleNamespace

import pytest

from app.config import settings
from app.embeddings import local
from app.embeddings.gemini import EmbeddingError
from app.indexing.embedder import CodeEmbedder
from app.repositories.paths import allowed_source


def test_local_embeddings_use_distinct_prefixes_without_cloud_client(monkeypatch):
    requests = []

    class Client:
        def __init__(self, **kwargs):
            pass
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def post(self, path, json):
            requests.append(json)
            return SimpleNamespace(raise_for_status=lambda: None, json=lambda: {"embeddings": [[1, 2, 3] for _ in json["input"]]})

    monkeypatch.setattr(local.httpx, "Client", Client)
    monkeypatch.setattr(settings, "EMBEDDING_PROVIDER", "local")
    monkeypatch.setattr(settings, "EMBEDDING_DIMENSION", 3)
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "")
    assert CodeEmbedder.embed_text("session") == [1, 2, 3]
    CodeEmbedder.embed_batch(["def session(): pass"])
    assert requests[0]["input"] == ["search_query: session"]
    assert requests[1]["input"] == ["search_document: def session(): pass"]
    assert requests[0]["truncate"] is False
    monkeypatch.setattr(settings, "EMBEDDING_DIMENSION", 768)
    with pytest.raises(EmbeddingError):
        CodeEmbedder.embed_text("wrong dimension")


def test_ingestion_rejects_symlinks_outside_root_and_secret_paths(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    source = root / "app.py"
    source.write_text("pass")
    assert allowed_source(root, source)
    secret = root / ".env.py"
    secret.write_text("secret")
    assert not allowed_source(root, secret)
    outside = tmp_path / "outside.py"
    outside.write_text("private")
    link = root / "link.py"
    link.symlink_to(outside)
    assert not allowed_source(root, link)
