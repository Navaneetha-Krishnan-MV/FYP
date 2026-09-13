"""Reject mixed embedding spaces, including same-dimension model switches."""
import httpx

from app.config import settings


def embedding_fingerprint() -> dict:
    if settings.EMBEDDING_PROVIDER == "cloud":
        return {
            "provider": "cloud", "model": settings.EMBEDDING_MODEL_NAME,
            "dimension": settings.EMBEDDING_DIMENSION, "preprocessing": "gemini-code-v1",
            "max_chars": settings.EMBEDDING_MAX_CHARS,
        }
    response = httpx.get(
        settings.OLLAMA_BASE_URL.rstrip("/") + "/api/tags", timeout=10, trust_env=False,
    )
    response.raise_for_status()
    name = settings.LOCAL_EMBEDDING_MODEL
    names = {name, name if ":" in name else name + ":latest"}
    model = next((m for m in response.json()["models"] if m["name"] in names), None)
    if model is None:
        raise RuntimeError(f"Local embedding model is not installed: {name}")
    return {
        "provider": "local", "model": name, "digest": model["digest"],
        "dimension": settings.EMBEDDING_DIMENSION, "preprocessing": "ollama-prefix-v1",
        "max_chars": settings.EMBEDDING_MAX_CHARS,
    }


def require_compatible(stored: dict | None, current: dict) -> None:
    if not stored or stored != current:
        raise RuntimeError("REINDEX_REQUIRED: embedding provider/model changed or index provenance is missing. Reindex this project.")
