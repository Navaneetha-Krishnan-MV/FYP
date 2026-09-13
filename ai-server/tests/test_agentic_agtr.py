"""AGTR integration invariants, independent of providers and external services."""
import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from app.agents.budgets import Budget
from app.agents.graph import build_investigation
from app.analysis.agtr import calculate_agtr_weights_adaptive, normalize_scores
from app.analysis.agentic_agtr import AgenticAGTR, persist_ranking, ranking_columns
from app.analysis.git_scorer import compute_git_temporal_scores
from app.config import settings
from app.llm.structured_output import ModelOutputError
from app.tools.executor import ToolExecutor
from test_agentic_mvp import FakeRepository, ScriptedGateway


class RankingRepository(FakeRepository):
    index = {"generation": "snapshot-1", "revision": "abc", "has_git": True}

    def __init__(self, *, graph=True, semantic=True, git=True):
        super().__init__()
        self.graph, self.semantic, self.git = graph, semantic, git
        self.semantic_calls = []
        self.cutoffs = []

    def chunk(self, chunk_id):
        return {**super().chunk("chunk-1"), "chunk_id": chunk_id, "function_name": chunk_id}

    def score_semantic_candidates(self, query, chunk_ids):
        self.semantic_calls.append((query, set(chunk_ids)))
        if not self.semantic:
            raise ConnectionError("Embedding service unavailable")
        return {cid: {"chunk-1": .8, "chunk-2": .7, "chunk-3": .6}.get(cid, .1) for cid in chunk_ids}

    def ranking_graph(self):
        if not self.graph:
            raise ConnectionError("Neo4j unavailable")
        return [("chunk-1", "chunk-2"), ("chunk-2", "chunk-3")]

    def score_git_candidates(self, candidates, search_terms, as_of):
        self.cutoffs.append(as_of)
        return [{**c, "git_score": .95 if c["chunk_id"] == "chunk-3" else .1} for c in candidates], [], self.git


def make_ranker(repo):
    tools = ToolExecutor(repo, Budget())
    # Previously collected via different tool/query; ranking must overwrite these scores.
    tools.candidates = {cid: {**repo.chunk(cid), "semantic_score": old} for cid, old in [("chunk-2", 1), ("chunk-1", .01)]}
    cutoff = datetime(2025, 1, 15, tzinfo=timezone.utc)
    return AgenticAGTR(tools, as_of=cutoff)


def test_real_legacy_fusion_over_canonical_expanded_pool():
    repo = RankingRepository()
    ranker = make_ranker(repo)
    result = ranker.rank("canonical bug", ["expiry"], 1)
    candidates = result["ranked_candidates"]
    assert {c["chunk_id"] for c in candidates} == {"chunk-1", "chunk-2", "chunk-3"}
    assert {c["chunk_id"]: c["semantic_score"] for c in candidates} == {"chunk-1": .8, "chunk-2": .7, "chunk-3": .6}
    assert repo.semantic_calls == [("canonical bug", {"chunk-1", "chunk-2"}), ("canonical bug", {"chunk-1", "chunk-2", "chunk-3"})]
    assert result["semantic_gap"] == .1
    assert result["hops_used"] == 3
    assert result["dependency_paths"]
    assert all(result["signal_availability"].values())
    weights = result["agtr_weights"]
    assert sum(weights.values()) == pytest.approx(1)
    legacy = calculate_agtr_weights_adaptive(*result["signal_gaps"].values())
    assert list(weights.values()) == pytest.approx([w / sum(legacy) for w in legacy], abs=1e-6)
    normalized = [normalize_scores([c[name + "_score"] for c in candidates]) for name in ("semantic", "graph", "git")]
    for i, candidate in enumerate(candidates):
        assert candidate["agtr_score"] == pytest.approx(sum(w * channel[i] for w, channel in zip(weights.values(), normalized)), abs=.001)
    assert repo.cutoffs == [ranker.as_of]
    assert list(ranker.tools.candidates) == [c["chunk_id"] for c in candidates]


@pytest.mark.parametrize("semantic,graph,git", [(True, False, False), (False, True, False), (False, False, False)])
def test_unavailable_signals_never_receive_weight_or_fake_scores(semantic, graph, git):
    result = make_ranker(RankingRepository(semantic=semantic, graph=graph, git=git)).rank("bug", [], 1)
    assert result["signal_availability"] == dict(zip(("semantic", "graph", "git"), (semantic, graph, git)))
    for name, weight in zip(("semantic", "graph", "git"), ("ws", "wg", "wt")):
        if not result["signal_availability"][name]:
            assert result["agtr_weights"][weight] == 0
            assert all(c[name + "_score"] == 0 for c in result["ranked_candidates"])
    if not any((semantic, graph, git)):
        assert [c["chunk_id"] for c in result["ranked_candidates"]] == ["chunk-1", "chunk-2"]
        assert any("not a meaningful" in w for w in result["warnings"])
    else:
        assert sum(result["agtr_weights"].values()) == 1


def test_incomplete_semantic_pool_disables_entire_channel(monkeypatch):
    repo = RankingRepository(graph=False, git=False)
    monkeypatch.setattr(repo, "score_semantic_candidates", lambda query, ids: {ids[0]: .99})
    result = make_ranker(repo).rank("bug", [], 1)
    assert result["agtr_weights"]["ws"] == 0
    assert all(c["semantic_score"] == 0 for c in result["ranked_candidates"])


def test_graph_expansion_is_bounded_and_reranking_keeps_cutoff(monkeypatch):
    monkeypatch.setattr(settings, "AGTR_MAX_CANDIDATES", 20)
    repo = RankingRepository()
    monkeypatch.setattr(repo, "ranking_graph", lambda: [("chunk-1", f"neighbor-{i}") for i in range(50)])
    ranker = make_ranker(repo)
    first = ranker.rank("bug", [], 1)
    second = ranker.rank("bug", [], 2)
    assert len(first["ranked_candidates"]) == len(second["ranked_candidates"]) == 20
    assert any("limit reached" in w for w in first["warnings"])
    assert first["as_of"] == second["as_of"]
    assert repo.cutoffs == [ranker.as_of, ranker.as_of]


def test_targeted_discovery_can_replace_graph_tail_in_a_full_pool(monkeypatch):
    monkeypatch.setattr(settings, "AGTR_MAX_CANDIDATES", 20)
    repo = RankingRepository()
    tools = ToolExecutor(repo, Budget())
    tools.remember_candidate(repo.chunk("chunk-1"))
    for i in range(19):
        tools.candidates[f"graph-{i}"] = repo.chunk(f"graph-{i}")
    assert tools.remember_candidate(repo.chunk("targeted-new-candidate"))
    assert len(tools.candidates) == 20
    assert "targeted-new-candidate" in tools.candidates
    assert "chunk-1" in tools.candidates
    assert "graph-18" not in tools.candidates
    tools.discovered_candidates.update(tools.candidates)
    assert not tools.remember_candidate(repo.chunk("over-limit"))
    assert tools.candidate_limit_reached


class Cursor:
    def __init__(self, rows=()):
        self.rows, self.calls = rows, []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def execute(self, sql, args):
        self.calls.append((sql, args))

    def fetchall(self):
        return self.rows

    def close(self):
        pass


def test_atomic_persistence_uses_same_pool_scores_and_weights():
    result = make_ranker(RankingRepository()).rank("bug", [], 1)
    columns = ranking_columns(result)
    cursor = Cursor()
    persist_ranking(SimpleNamespace(cursor=lambda: cursor), "analysis-only", result, {"ranking_history": [result]})
    assert len(cursor.calls) == 1
    sql, args = cursor.calls[0]
    assert "WHERE id=%s" in sql and args[-1] == "analysis-only"
    for i, name in enumerate(("semanticScores", "graphScores", "gitScores", "finalRanking", "agtrWeights")):
        assert json.loads(args[i]) == columns[name]
    ids = {c["chunkId"] for c in columns["finalRanking"]}
    assert all({c["chunkId"] for c in columns[name]} == ids for name in ("semanticScores", "graphScores", "gitScores"))
    assert json.loads(args[-2])["ranking_history"][0]["agtr_weights"] == columns["agtrWeights"]


def test_strict_temporal_scoring_anchors_time_and_does_not_align_old_hunks():
    cutoff = datetime(2025, 1, 15, tzinfo=timezone.utc)
    candidate = {"file_path": "session.py", "start_line": 1, "end_line": 2}
    patch = "@@ -1,2 +1,2 @@\n-old\n+new"
    cursor = Cursor([("old", "author", "change", cutoff - timedelta(days=10), "session.py", patch)])
    metadata = {}
    conn = SimpleNamespace(cursor=lambda: cursor)
    scores, _ = compute_git_temporal_scores("project", [dict(candidate)], [], connection=conn, as_of=cutoff,
                                           strict=True, aligned_revision="current", metadata=metadata)
    assert scores[0]["git_score"] == .091  # .15 * exp(-.05*10), not .30 for unrelated historic coordinates
    assert metadata["available"] is True
    sql, args = cursor.calls[0]
    assert 'c."committedAt" <= %s' in sql
    assert args == ("project", cutoff, ["session.py"])
    cursor.rows = [("current", "author", "change", cutoff, "session.py", patch)]
    scores, _ = compute_git_temporal_scores("project", [dict(candidate)], [], connection=conn, as_of=cutoff,
                                           strict=True, aligned_revision="current")
    assert scores[0]["git_score"] == .3


@pytest.mark.parametrize("rationale", ["Source comparison is inverted despite lower semantic similarity.", ""])
def test_lower_rank_requires_explanation_and_retains_selection(rationale):
    class TwoCandidates(FakeRepository):
        def chunk(self, cid):
            return {**super().chunk("chunk-1"), "chunk_id": cid}

        def keyword_search(self, query, limit=5):
            return [self.chunk("chunk-1"), self.chunk("chunk-2")]

        def score_semantic_candidates(self, query, ids):
            return {cid: .9 if cid == "chunk-2" else .5 for cid in ids}

    class LowerRankGateway(ScriptedGateway):
        def generate(self, role, payload, schema):
            if role == "reason":
                assert [c["chunk_id"] for c in payload["candidates"]] == ["chunk-2", "chunk-1"]
                assert payload["candidates"][0]["agtr_score"] == 1
                result = super().generate(role, payload, schema)
                result.hypotheses[0].ranking_rationale = rationale
                return result
            return super().generate(role, payload, schema)

    tools = ToolExecutor(TwoCandidates(), Budget())
    graph = build_investigation(LowerRankGateway(tools), tools)
    if not rationale:
        with pytest.raises(ModelOutputError, match="ranking disagreement"):
            graph.invoke({"bug": {"description": "expired"}})
    else:
        result = graph.invoke({"bug": {"description": "expired"}})
        assert result["report"]["selected_candidate_rank"] == 2
        assert result["report"]["ranking_rationale"] == rationale
        assert result["agtr_ranking"]["ranked_candidates"][0]["chunk_id"] == "chunk-2"
