"""Reasoning provider selection is independent of embedding configuration."""
from app.config import settings


def create_chat_model(*, timeout: float | None = None, json_schema=None, action=False):
    timeout = timeout or settings.LLM_TIMEOUT_SECONDS
    if settings.REASONING_PROVIDER == "local":
        from langchain_ollama import ChatOllama
        return ChatOllama(
            model=settings.LOCAL_REASONING_MODEL, base_url=settings.OLLAMA_BASE_URL,
            temperature=0, num_ctx=8192, num_predict=min(settings.LLM_MAX_OUTPUT_TOKENS, 512 if action else 1500),
            format=json_schema if settings.LOCAL_JSON_SCHEMA and json_schema else "json",
            client_kwargs={"timeout": timeout, "trust_env": False},
        )
    if not settings.GEMINI_API_KEY:
        raise RuntimeError("Cloud reasoning requires GEMINI_API_KEY in ai-server/.env")
    from langchain_google_genai import ChatGoogleGenerativeAI
    return ChatGoogleGenerativeAI(
        model=settings.GEMINI_MODEL_NAME, api_key=settings.GEMINI_API_KEY,
        max_tokens=settings.LLM_MAX_OUTPUT_TOKENS, timeout=timeout, max_retries=0,
        response_mime_type="application/json",
        **({"thinking_level": "low"} if settings.GEMINI_MODEL_NAME.startswith("gemini-3") else {}),
    )


def reasoning_profile():
    return {"provider": settings.REASONING_PROVIDER,
            "model": settings.LOCAL_REASONING_MODEL if settings.REASONING_PROVIDER == "local" else settings.GEMINI_MODEL_NAME}
