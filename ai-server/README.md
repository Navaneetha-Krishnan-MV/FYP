Run:

```bash
uv run uvicorn main:app --reload --port 8000
```

Embedding readiness:

```bash
curl http://localhost:8000/api/health/embedding
```

This endpoint loads the configured Sentence Transformer, runs a probe inference,
and verifies that its vector size matches `EMBEDDING_DIMENSION`. Pipeline stage,
batch progress, exception type, reason, and traceback are written to
`logs/ai-server.log`. A failed indexing run also stores its error ID, stage,
exception type, and reason in `Project.errorMsg`.

The default configuration uses the local Hugging Face model cache to avoid remote
metadata retry loops. On a new machine, download the model once with network
access and `EMBEDDING_LOCAL_FILES_ONLY=false`; production can then set it back to
`true`.
