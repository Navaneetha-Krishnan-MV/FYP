"""Ollama embedding transport. Nomic uses distinct query/document prefixes."""
import math

import httpx

from app.config import settings


def embed_local(texts: list[str], *, query: bool = False) -> list[list[float]]:
    if not texts:
        return []
    from app.embeddings.gemini import EmbeddingError

    prefix = ""
    if settings.LOCAL_EMBEDDING_MODEL.split(":")[0] == "nomic-embed-text":
        prefix = "search_query: " if query else "search_document: "
    vectors = []
    with httpx.Client(base_url=settings.OLLAMA_BASE_URL, timeout=90, trust_env=False) as client:
        for start in range(0, len(texts), settings.EMBEDDING_BATCH_SIZE):
            batch = texts[start:start + settings.EMBEDDING_BATCH_SIZE]
            try:
                response = client.post("/api/embed", json={
                    "model": settings.LOCAL_EMBEDDING_MODEL,
                    "input": [prefix + text[:settings.EMBEDDING_MAX_CHARS] for text in batch],
                    "truncate": False,
                })
                response.raise_for_status()
                output = response.json()["embeddings"]
                if len(output) != len(batch) or any(
                    len(v) != settings.EMBEDDING_DIMENSION
                    or not all(isinstance(x, (float, int)) and math.isfinite(x) for x in v)
                    or not any(v) for v in output
                ):
                    raise ValueError("invalid vector count, dimension, or values")
                vectors.extend(output)
            except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
                raise EmbeddingError(
                    "Local embedding failed. Check Ollama, the installed model, "
                    "its input limit, and EMBEDDING_DIMENSION."
                ) from exc
    return vectors
