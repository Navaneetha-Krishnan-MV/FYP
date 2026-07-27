# AGTR Multi-Signal Scoring & Adaptive Weighting Redesign

## Context

AGTR (Adaptive Graph-Temporal Retrieval/Ranking) combines three signals per
candidate function — semantic similarity `S(v)`, graph structural score
`G(v)`, and git temporal score `T(v)` — into `AGTR(v) = ws*S(v) + wg*G(v) +
wt*T(v)`, then hands the top candidates to Gemini for root-cause reasoning.

While debugging a misidentified root cause (bug report: "Misleading login
message", project: ATM console app), we found two of the three signals were
non-functional for that run, while the weight formula had no way to detect
this:

1. **Graph score collapsed into an echo of semantic score.** The propagation
   formula (`seed_semantic_score * 0.5^hop_distance`, kept via `max()`
   against each node's own baseline) can never exceed an already-decent
   semantic score. In a small, semantically dense project, everything
   relevant is already a semantic seed, so `graph_score == semantic_score`
   for every candidate — the graph signal added zero discrimination despite
   holding the largest weight (`wg=0.46`).
2. **Temporal score flatlined.** The project was a ZIP upload with no `.git`
   directory, so `create_synthetic_git_history` produced one synthetic
   commit with zero `CommitChange` rows. Every candidate fell back to the
   same `0.1` baseline `git_score` — `wt=0.31`, the second-largest weight,
   contributed a uniform constant, i.e. no signal at all.
3. Separately (not project-specific): temporal scoring is keyed only by
   `file_path`. Every function in the same file gets an identical
   `git_score` regardless of which function a commit's diff actually
   touched, even though the stored diff patches contain unified-diff hunk
   headers with line ranges that go unused today.

Net effect: ~77% of the score's weight budget (`wg+wt`) was riding on dead
signal, and ranking was effectively decided by semantic similarity alone —
which itself had almost no spread (`Cs=0.0284`) among the top candidates.
The correct answer ranked #9; only widening the LLM's evidence window (a
separate, already-shipped fix) let Gemini see it.

This spec is a broader rework of the graph score, temporal score, and the
weight-update logic — not just a patch for the observed symptom — since this
is a core piece of the project's research contribution.

## Goals

- Graph score reflects real structural proximity to the semantic seed set,
  not just an echo of seed scores.
- Temporal score differentiates at function granularity where diff data
  supports it, not just file granularity.
- Weight allocation (`ws, wg, wt`) is adaptive for **all three** signals,
  not just semantic — a signal that isn't discriminating for a given
  project/query should lose its share of the weight automatically.
- Keep the existing confidence→weight mathematical framing (sigmoid over a
  "top candidate vs. mean of rest" gap) so the extension is a natural
  generalization of the current methodology, not a different paradigm.
- No DB schema changes. `agtrWeights` JSON shape (`{ws, wg, wt}`) is
  unchanged; only how the values are computed changes.

## Non-goals

- Hop-depth selection (`determine_adaptive_hops`) stays driven by `Cs` only.
  Making it also react to `Cg` would require restructuring the pipeline
  into an iterative/two-pass traversal (`Cg` doesn't exist until after
  traversal has already happened) — out of scope for this round.
- No learned/calibrated weighting (e.g. regression on labeled examples) —
  no labeled dataset exists to calibrate against, and a closed-form
  confidence-gap formula stays consistent with the existing methodology.
- No change to the semantic embedding pipeline (already migrated to Gemini
  separately).
- No change to `EMBEDDING_MAX_CHARS` or diff patch truncation (`[:3000]`
  chars per patch) — out of scope, though noted as a limitation below.

## Design

### 1. Graph score: Personalized PageRank

**File:** `app/analysis/graph_expander.py`

Replace the per-seed decay-and-max formula with Personalized PageRank over
an **undirected** graph of the project's `CALLS`/`DEPENDS_ON` edges
(undirected to match the existing Cypher traversal's undirected semantics —
`-[:CALLS|DEPENDS_ON*1..hops]-`, no arrow — since a function's structural
neighborhood legitimately includes both what it calls and what calls it).

Flow:
1. Fetch all `CALLS`/`DEPENDS_ON` edges for the project from Neo4j once,
   build a `networkx.Graph` (undirected) keyed by `chunkId`.
2. Build a personalization vector: `{chunk_id: semantic_score}` for every
   semantic seed, normalized to sum to 1 (nodes not in the seed set get 0
   restart probability — they can still accrue rank via graph structure).
3. Run `nx.pagerank(G, personalization=personalization, alpha=0.85)`
   (standard damping factor).
4. Keep today's existing hop-limited Neo4j traversal query to determine
   *which* nodes qualify as expanded candidates and to build
   `dependency_paths` (unchanged, still useful for the UI and for Gemini's
   evidence) — but assign each candidate's `graph_score` from the PageRank
   result instead of the decay formula.

**Error handling:** if Neo4j is unreachable, the graph has no edges, or
`nx.pagerank` fails to converge/raises — catch and fall back to today's
degenerate behavior (`graph_score = semantic_score`), matching the existing
try/except-and-continue pattern already used around the Neo4j call. Analysis
should degrade, not fail outright.

### 2. Temporal score: function-level relevance from diff hunks

**File:** `app/analysis/git_scorer.py`

Currently `file_git_stats` keeps only the single best-scoring commit per
`file_path`, and every candidate in that file inherits the same score.
Rework:

1. For each file, keep the list of (commit, patch, parsed hunk ranges) —
   not just the single best commit.
2. Parse unified-diff hunk headers (`@@ -a,b +c,d @@`) out of each stored
   patch (a patch may contain multiple hunks) to get post-change line
   ranges.
3. When scoring a candidate, scan that file's commits for hunk-range
   overlap against the candidate's `[start_line, end_line]`:
   - **Overlap found:** full relevance base (`0.3`, as today) + existing
     message/diff term-match bonuses, decayed by commit recency.
   - **File touched by this commit, no overlap with this function:**
     reduced relevance base of `0.15` (half of the `0.3` direct-hit base —
     file-level topical relevance without function-level evidence). Term-match
     bonuses (which indicate topical relevance regardless of exact lines)
     still apply on top of this reduced base.
   - **File never touched:** unchanged `0.1` fallback baseline.
   - Take the max resulting `t_score` across that file's commits, per
     candidate (same "best evidence wins" principle as today, just
     evaluated per-function instead of a single per-file winner).

**Known limitation to document, not fix here:** patches are truncated to
3000 chars at ingestion (`git_indexer.py`); a hunk beyond that truncation
point won't be visible to the overlap check. Line-range matching against
*current* chunk boundaries is also an approximation — if the file has been
edited since the commit in question, line numbers can drift. Both are
acceptable for this round; noting them for the writeup.

### 3. Weight logic: generalize confidence-gap to all three signals

**File:** `app/analysis/agtr.py`

Generalize `compute_retrieval_confidence` into a reusable
`compute_confidence_gap(scores: List[float]) -> float` (same formula:
`top1 - mean(rest)`, clamped at 0), used for all three signal types:

```
Cs = compute_confidence_gap([c.semantic_score for c in candidates])
Cg = compute_confidence_gap([c.graph_score for c in candidates])
Ct = compute_confidence_gap([c.git_score for c in candidates])
```

Replace `calculate_agtr_weights(C)` with
`calculate_agtr_weights_adaptive(Cs, Cg, Ct, k=10.0, theta=0.15)`:

```python
def sigmoid_conf(C, k, theta):
    return 1.0 / (1.0 + exp(-k * (C - theta)))

raw_s, raw_g, raw_t = sigmoid_conf(Cs), sigmoid_conf(Cg), sigmoid_conf(Ct)
total = raw_s + raw_g + raw_t
if total == 0:
    return 1/3, 1/3, 1/3   # degenerate case: no signal discriminates at all
return raw_s/total, raw_g/total, raw_t/total
```

This directly fixes the observed bug: a flat/zero-variance signal (like
`Ct=0` for a project with no real git history) produces a near-zero raw
weight and gets renormalized down toward 0, instead of statically claiming
31% of the score.

**Pipeline reordering required** (`app/analysis/pipeline.py`): weight
computation must move from immediately after semantic retrieval to
immediately before `rank_candidates_agtr`, since `Cg`/`Ct` aren't knowable
until graph expansion and git scoring have both run. New order:

```
1. semantic_seeds = search_semantic_candidates(...)
2. Cs = compute_confidence_gap(semantic scores)      # unchanged position
3. hops = determine_adaptive_hops(Cs)                 # unchanged
4. expanded_candidates, dependency_paths = expand_graph_neighbors(..., hops)
5. scored_candidates, git_commits = compute_git_temporal_scores(...)
6. Cg = compute_confidence_gap(graph scores)          # NEW
   Ct = compute_confidence_gap(git scores)            # NEW
   ws, wg, wt = calculate_agtr_weights_adaptive(Cs, Cg, Ct)   # MOVED here
7. final_ranked = rank_candidates_agtr(scored_candidates, ws, wg, wt)
```

`confidence_label`/`confidence_val` (HIGH/MEDIUM/LOW, shown in the UI) stay
derived from `Cs` alone, unchanged — that label is specifically about
semantic retrieval confidence, not the combined signal.

## Testing

No test suite exists in `ai-server` yet. Add `pytest` as a dev dependency
and cover the pieces that are pure functions (no live DB/Neo4j needed):

- `tests/test_agtr_weights.py` — confidence-gap computation; sigmoid +
  renormalization always sums to ~1.0; the zero-signal-everywhere fallback;
  and a direct regression test encoding the bug found here (a
  zero-variance signal's weight collapses toward 0).
- `tests/test_git_scorer.py` — hunk-header regex parsing (single hunk,
  multiple hunks, no hunks/malformed patch) and line-range overlap logic,
  as standalone functions extracted for testability.
- `tests/test_graph_expander.py` — personalized PageRank over a small
  synthetic `networkx.Graph`: a node adjacent to a high-weight seed ranks
  above a distant/unconnected node; graceful fallback on an empty graph.

After implementation, re-verify end-to-end against the two already-indexed
live projects used during debugging:
- **ATM console app** (zero real git history): confirm `wt` collapses
  toward ~0 instead of claiming ~31% of a dead signal, and that the
  previously-fixed root cause (`beginLoop`) is still correctly identified.
- **parking** (real GitHub history, 34 commits): confirm git scores now
  differentiate between functions within the same file instead of being
  uniform per file.

## Rollout

No schema/data migration needed — `agtrWeights` JSON shape is unchanged,
and every analysis run recomputes from scratch. `pytest` is a new dev-only
dependency (`uv add --dev pytest`), no runtime dependency change beyond
`networkx`, which is already present.
