Run:

```bash
uv run uvicorn main:app --reload --port 8000
```

Embedding readiness:

```bash
curl http://localhost:8000/api/health/embedding
```

This endpoint calls the configured Gemini embedding model and verifies that its
vector size matches `EMBEDDING_DIMENSION`. Repository chunks are sent with
Gemini's synchronous batch-embedding request, using `EMBEDDING_BATCH_SIZE` texts
per request. Calls from concurrent indexing jobs are serialized and paced by
`EMBEDDING_REQUESTS_PER_MINUTE`; set that value at or below the active model RPM
shown in Google AI Studio. Transient 408, 429, and 5xx responses use bounded
exponential backoff with jitter.

Pipeline stage, batch progress, exception type, reason, and traceback are written
to `logs/ai-server.log`. A failed indexing run also stores its error ID, stage,
exception type, and reason in `Project.errorMsg`.
