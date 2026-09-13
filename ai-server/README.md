# CodeLens AI service

The MVP uses LangGraph for bounded root-cause investigation and LangChain for
cloud/local reasoning and typed tools. Providers are independent:

```dotenv
REASONING_PROVIDER=cloud
EMBEDDING_PROVIDER=local
```

Cloud uses Gemini; local uses Ollama. Either switch accepts `cloud` or `local`.
Changing embeddings requires reindexing, even when dimensions stay the same.

From this directory, after configuring `.env` and the existing application database:

```bash
uv sync --frozen
uv run python -m app.cli setup
uv run python -m app.cli doctor --probe-model
```

Start the API and worker in separate terminals:

```bash
uv run uvicorn main:app --reload --port 8000
uv run python worker.py
```

Without the worker, submitted analyses remain queued. Interrupted jobs restart
with an attempt limit; the MVP does not resume LangGraph checkpoints.

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 uv run pytest -q
```

See [the implemented MVP guide](../docs/agentic-rca-mvp.md) for setup, provider
combinations, architecture, tools, prompts, live testing and limitations.
