"""Legacy AGTR math applied to the accumulated, snapshot-scoped agent pool."""
from datetime import datetime, timezone
import logging
import math

import networkx as nx

from app.analysis.agtr import (
    compute_confidence_gap, compute_zscore_gap, calculate_agtr_weights_adaptive,
    determine_adaptive_hops, rank_candidates_agtr,
)
from app.analysis.graph_expander import compute_personalized_pagerank
from app.config import settings

logger = logging.getLogger(__name__)
SIGNALS = ("semantic", "graph", "git")


def adaptive_available_weights(candidates, available):
    gaps = {name: compute_zscore_gap([c[name + "_score"] for c in candidates]) for name in SIGNALS}
    raw = calculate_agtr_weights_adaptive(*(gaps[name] for name in SIGNALS))
    masked = [weight if available[name] else 0.0 for name, weight in zip(SIGNALS, raw)]
    total = sum(masked)
    values = [round(weight / total, 6) for weight in masked] if total else [0.0] * 3
    if total:
        largest = max(range(3), key=values.__getitem__)
        values[largest] = round(values[largest] + 1 - sum(values), 6)
    return dict(zip(("ws", "wg", "wt"), values)), gaps


class AgenticAGTR:
    def __init__(self, tools, as_of=None):
        self.tools, self.repository = tools, tools.repository
        self.as_of = as_of or datetime.now(timezone.utc)

    def rank(self, query, search_terms, round_number):
        self.tools.guard()
        self.tools.budget.check()
        pool = {cid: {**c, "semantic_score": 0.0, "graph_score": 0.0, "git_score": 0.0}
                for cid, c in sorted(self.tools.candidates.items())}
        available = dict.fromkeys(SIGNALS, False)
        warnings, paths, commits = [], [], []
        if self.tools.candidate_limit_reached:
            warnings.append("Candidate limit reached; some agent discoveries were omitted from the ranked pool.")
        semantic_pool = set()
        hops, semantic_gap = 0, 0.0

        def semantic():
            nonlocal semantic_pool
            semantic_pool = set(pool)
            if not pool:
                return False
            try:
                scores = self.repository.score_semantic_candidates(query, list(pool))
                if set(scores) != set(pool) or any(not math.isfinite(v) for v in scores.values()):
                    raise ValueError("Incomplete canonical semantic scores")
                for cid, c in pool.items():
                    c["semantic_score"] = max(0.0, min(1.0, scores[cid]))
                return True
            except Exception:
                logger.exception("agtr_semantic_unavailable")
                warnings.append("Semantic scoring unavailable or incomplete; its weight is zero.")
                for c in pool.values():
                    c["semantic_score"] = 0.0
                return False

        available["semantic"] = semantic()
        seed_scores = {cid: c["semantic_score"] for cid, c in pool.items()}
        semantic_gap = compute_confidence_gap(list(seed_scores.values()))
        if pool:
            try:
                edges = self.repository.ranking_graph()
                if edges:
                    hops = determine_adaptive_hops(semantic_gap)
                    graph = nx.Graph(edges)
                    # Deterministic bounded expansion, preserving every agent-discovered candidate.
                    discovered = {}
                    for cid in sorted(pool, key=lambda cid: (-seed_scores[cid], cid)):
                        if cid not in graph:
                            continue
                        for target, path in nx.single_source_shortest_path(graph, cid, cutoff=hops).items():
                            if target != cid and (target not in discovered or len(path) < len(discovered[target])):
                                discovered[target] = path
                    for cid in sorted(discovered, key=lambda cid: (len(discovered[cid]), cid)):
                        if cid not in pool and len(pool) < settings.AGTR_MAX_CANDIDATES:
                            pool[cid] = {**self.repository.chunk(cid), "semantic_score": 0.0, "graph_score": 0.0, "git_score": 0.0}
                    if any(cid not in pool for cid in discovered):
                        warnings.append("Candidate limit reached; graph expansion was truncated.")
                    if set(pool) != set(seed_scores):
                        available["semantic"] = semantic()
                    # Exactly the legacy undirected personalized PageRank algorithm.
                    # Uniform seed mass is explicit when semantic embeddings are unavailable/flat zero.
                    personalization = seed_scores if available["semantic"] and sum(seed_scores.values()) > 0 else dict.fromkeys(seed_scores, 1.0)
                    if not available["semantic"] or sum(seed_scores.values()) == 0:
                        warnings.append("PageRank used uniform seed mass because semantic seed scores were unavailable or zero.")
                    scores = compute_personalized_pagerank(edges, personalization)
                    available["graph"] = bool(scores)
                    for cid, c in pool.items():
                        c["graph_score"] = scores.get(cid, 0.0)
                    paths = [" -> ".join(pool[cid]["function_name"] if cid in pool else cid for cid in path)
                             for target, path in sorted(discovered.items()) if target in pool][:10]
                else:
                    warnings.append("Dependency graph has no edges; graph weight is zero.")
            except Exception:
                logger.exception("agtr_graph_unavailable")
                warnings.append("Graph scoring unavailable; no semantic-score substitution was used.")
                hops = 0
                paths = []
                for c in pool.values():
                    c["graph_score"] = 0.0
                available["graph"] = False

        # Also covers a partially failed graph expansion: no discovered candidate
        # inherits an absent/zero semantic score merely because its source was graph search.
        if set(pool) != semantic_pool:
            available["semantic"] = semantic()

        if pool and self.repository.index["has_git"]:
            try:
                scored, commits, available["git"] = self.repository.score_git_candidates(list(pool.values()), search_terms, self.as_of)
                pool = {c["chunk_id"]: c for c in scored}
                warnings.append("Historical diff overlap is function-level only at the pinned revision; older commits use file-level relevance."
                                if available["git"] else "No eligible Git changes for these candidates before the analysis cutoff; temporal weight is zero.")
            except Exception:
                logger.exception("agtr_git_unavailable")
                warnings.append("Git scoring unavailable; its weight is zero.")
        elif pool:
            warnings.append("No Git history in this index; temporal weight is zero.")
        for name in SIGNALS:
            if not available[name]:
                for c in pool.values():
                    c[name + "_score"] = 0.0
        # Compute comparable signal gaps over the SAME final pool, then reuse legacy fusion.
        weights, gaps = adaptive_available_weights(list(pool.values()), available)
        if not any(available.values()):
            warnings.append("No ranking signals available; the zero-score order is not a meaningful AGTR ranking.")
        ranked = rank_candidates_agtr([pool[cid] for cid in sorted(pool)], **weights)
        self.tools.guard()
        self.tools.budget.check()
        self.tools.candidates = {c["chunk_id"]: c for c in ranked}
        return {"version": "agent-agtr-v1", "round": round_number, "query": query,
                "as_of": self.as_of.isoformat(), "ranked_candidates": ranked,
                "agtr_weights": weights, "signal_gaps": gaps, "signal_availability": available,
                "semantic_gap": semantic_gap, "hops_used": hops, "dependency_paths": paths,
                "git_commits": commits, "warnings": list(dict.fromkeys(warnings))}


def ranking_columns(ranking):
    """One projection shared by progress writes and final AnalysisResult output."""
    candidates = ranking["ranked_candidates"]
    return {
        **{name + "Scores": [{"chunkId": c["chunk_id"], "score": c[name + "_score"]} for c in candidates] for name in SIGNALS},
        "finalRanking": [{"chunkId": c["chunk_id"], "filePath": c["file_path"], "functionName": c["function_name"],
                          "rank": c["rank"], "agtrScore": c["agtr_score"], "semanticScore": c["semantic_score"],
                          "graphScore": c["graph_score"], "gitScore": c["git_score"]} for c in candidates],
        "agtrWeights": ranking["agtr_weights"], "semanticGap": ranking["semantic_gap"], "hopsUsed": ranking["hops_used"],
    }


def persist_ranking(conn, analysis_id, ranking, context):
    import json
    values = ranking_columns(ranking)
    with conn.cursor() as cur:
        cur.execute('''UPDATE "AnalysisResult" SET "semanticScores"=%s::json,
            "graphScores"=%s::json, "gitScores"=%s::json, "finalRanking"=%s::json,
            "agtrWeights"=%s::json, "semanticGap"=%s, "hopsUsed"=%s,
            "dependencyPath"=%s, "evidenceContext"=%s::json WHERE id=%s''', (
            *(json.dumps(values[key]) for key in ("semanticScores", "graphScores", "gitScores", "finalRanking", "agtrWeights")),
            values["semanticGap"], values["hopsUsed"], "\n".join(ranking["dependency_paths"]) or None,
            json.dumps(context, default=str), analysis_id,
        ))
