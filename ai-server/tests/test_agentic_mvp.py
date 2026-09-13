import json
from types import SimpleNamespace

import pytest

from app.agents.budgets import Budget
from app.agents.contracts import AgentAction, BugSignals
from app.agents.graph import build_investigation
from app.config import Settings, settings
from app.embeddings.fingerprint import require_compatible
from app.llm.structured_output import ModelGateway, ModelOutputError, parse_json
from app.tools.executor import ToolExecutor


class FakeRepository:
    index = {"generation": "snapshot-1", "revision": "abc", "has_git": False}

    def __init__(self):
        self.reads = 0

    def chunk(self, chunk_id):
        if chunk_id != "chunk-1":
            raise ValueError("Unknown chunk in this project")
        return {"chunk_id": chunk_id, "file_path": "session.py", "function_name": "expired",
                "start_line": 1, "end_line": 2, "code_content": "def expired(now, expiry):\n    return now < expiry"}

    def keyword_search(self, query, limit=5):
        return [self.chunk("chunk-1")]

    def semantic_search(self, query, limit=5):
        return [{**self.chunk("chunk-1"), "semantic_score": 0.9}]

    def read_code(self, chunk_id, offset=0, lines=80):
        self.reads += 1
        return self.chunk(chunk_id)

    def git_history(self, chunk_id, limit=3):
        raise LookupError("No Git history")

    def dependency_neighbors(self, chunk_id):
        return []


def test_provider_switches_are_independent():
    for reasoning in ("cloud", "local"):
        for embedding in ("cloud", "local"):
            config = Settings(_env_file=None, REASONING_PROVIDER=reasoning, EMBEDDING_PROVIDER=embedding)
            assert (config.REASONING_PROVIDER, config.EMBEDDING_PROVIDER) == (reasoning, embedding)
    with pytest.raises(ValueError):
        Settings(_env_file=None, REASONING_PROVIDER="auto")
    assert Settings(_env_file=None, EMBEDDING_DIMENSION="768").EMBEDDING_DIMENSION == 768
    with pytest.raises(ValueError):
        Settings(_env_file=None, EMBEDDING_DIMENSION="1024")


def test_same_dimension_different_embedding_model_requires_reindex():
    with pytest.raises(RuntimeError, match="REINDEX_REQUIRED"):
        require_compatible({"model": "a", "dimension": 768}, {"model": "b", "dimension": 768})
    require_compatible({"model": "a"}, {"model": "a"})


def test_tool_allowlist_schema_ownership_and_cache():
    repo = FakeRepository()
    tools = ToolExecutor(repo, Budget())
    assert tools.execute("git", "semantic_search", {"query": "session"})["status"] == "error"
    assert tools.execute("code", "read_code", {"chunk_id": "chunk-1", "project_id": "other"})["status"] == "error"
    assert tools.execute("code", "read_code", {"chunk_id": "other-project-chunk"})["status"] == "error"
    observation = tools.execute("code", "read_code", {"chunk_id": "chunk-1"})
    assert observation["status"] == "ok"
    assert tools.has_code("chunk-1", observation["evidence_ids"])
    assert tools.execute("code", "read_code", {"chunk_id": "chunk-1"})["cached"]
    assert repo.reads == 2  # one rejected source ID, one real read
    with pytest.raises(ValueError, match="unknown evidence"):
        tools.validate_refs(["invented"])


def test_json_contract_rejects_ambiguous_or_extra_output():
    valid = {"response": {"action": "tool", "tool": "read_code", "arguments": {"chunk_id": "chunk-1"}}}
    assert parse_json(json.dumps(valid), AgentAction).response.tool == "read_code"
    for text in (json.dumps(valid) + " More text", '{"response":{"action":"shell","command":"ls"}}', '{"summary":"s","search_terms":[],"extra":true}'):
        with pytest.raises(ValueError):
            parse_json(text, AgentAction)


def test_model_json_repair_is_bounded_and_counted():
    class BadModel:
        def invoke(self, messages):
            return SimpleNamespace(content="not JSON")
    budget = Budget()
    gateway = ModelGateway(budget, model=BadModel())
    with pytest.raises(ModelOutputError, match="one repair"):
        gateway.generate("understand", {"bug": "broken"}, BugSignals)
    assert budget.llm_calls == 2


def test_transient_provider_retry_is_counted(monkeypatch):
    from app.llm import structured_output
    class RetryModel:
        count = 0
        def invoke(self, messages):
            self.count += 1
            if self.count == 1:
                raise ConnectionError("transient")
            return SimpleNamespace(content='{"summary":"bug","search_terms":[]}')
    monkeypatch.setattr(structured_output.time, "sleep", lambda _: None)
    budget = Budget()
    result = ModelGateway(budget, model=RetryModel()).generate("understand", {}, BugSignals)
    assert result.summary == "bug"
    assert budget.llm_calls == 2


def test_cloud_pacing_cannot_outwait_deadline(monkeypatch):
    import time
    from app.llm.rate_limit import CloudRequestPacer
    from app.agents.budgets import BudgetExceeded
    monkeypatch.setattr(CloudRequestPacer, "_next_at", time.monotonic() + settings.RCA_MAX_SECONDS + 1)
    with pytest.raises(BudgetExceeded):
        CloudRequestPacer.wait(Budget())


def test_daily_quota_is_not_retried():
    from app.llm.rate_limit import transient_error, provider_error_message
    exc = RuntimeError("429 GenerateRequestsPerDayPerProjectPerModel-FreeTier")
    assert not transient_error(exc)
    assert "daily quota" in provider_error_message(exc)


class ScriptedGateway:
    def __init__(self, tools, *, followup=False, invented=False):
        self.tools, self.followup, self.invented = tools, followup, invented
        self.verifications = 0

    def generate(self, role, payload, schema):
        self.tools.budget.take("llm")
        if role == "understand":
            data = {"summary": "expired session remains valid", "search_terms": ["expired"]}
        elif role in {"code", "git", "dependency"}:
            data = {"response": {"action": "finish", "result": {"summary": "Inspect the expiry condition", "evidence_ids": []}}}
        elif role == "reason":
            eid = next(iter(self.tools.evidence))
            data = {"hypotheses": [{"candidate_id": "chunk-1", "mechanism": "Comparison is inverted",
                                   "evidence_ids": [eid], "suggested_fix": "Compare now >= expiry"}]}
        else:
            self.verifications += 1
            data = {"verdict": "insufficient_evidence" if self.followup else "supported",
                    "primary_candidate_id": "chunk-1", "evidence_ids": ["invented" if self.invented else next(iter(self.tools.evidence))],
                    "explanation": "Check the comparison", "follow_up": [{"role": "code", "question": "Check caller"}] if self.followup else []}
        return schema.model_validate(data)


def test_graph_supported_result_requires_real_code_evidence():
    tools = ToolExecutor(FakeRepository(), Budget())
    graph = build_investigation(ScriptedGateway(tools), tools)
    result = graph.invoke({"bug": {"description": "Session expires incorrectly"}})
    assert result["report"]["outcome"] == "supported_hypothesis"
    assert result["report"]["runtime_verified"] is False
    assert tools.evidence


def test_graph_reinvestigates_then_stops_when_no_new_evidence():
    tools = ToolExecutor(FakeRepository(), Budget())
    gateway = ScriptedGateway(tools, followup=True)
    result = build_investigation(gateway, tools).invoke({"bug": {"description": "Session"}})
    assert gateway.verifications == 2
    assert result["report"]["rounds_used"] == 2
    assert result["report"]["outcome"] == "inconclusive"


def test_graph_rejects_invented_verifier_evidence():
    tools = ToolExecutor(FakeRepository(), Budget())
    with pytest.raises(ValueError, match="unknown evidence"):
        build_investigation(ScriptedGateway(tools, invented=True), tools).invoke({"bug": {"description": "Session"}})


def test_graph_finalizes_without_more_model_calls_when_budget_exhausted(monkeypatch):
    monkeypatch.setattr(settings, "RCA_MAX_LLM_CALLS", 1)
    tools = ToolExecutor(FakeRepository(), Budget())
    result = build_investigation(ScriptedGateway(tools), tools).invoke({"bug": {"description": "Session"}})
    assert result["report"]["outcome"] == "inconclusive"
    assert result["report"]["termination_reason"] == "budget_exhausted"
    assert tools.budget.llm_calls == 1
