import math
from typing import List, Dict, Any, Tuple

def compute_confidence_gap(scores: List[float]) -> float:
    """
    Generic confidence gap used for all three AGTR signals (semantic,
    graph, temporal): how much does the top score separate from the mean
    of the rest? C = top1 - mean(rest), clamped at 0.

    Sorts internally rather than assuming scores[0] is the top score -
    semantic candidate lists arrive pre-sorted by similarity, but graph
    and temporal score lists don't share that guarantee.
    """
    if not scores:
        return 0.0
    if len(scores) == 1:
        return round(float(scores[0]), 4)

    ordered = sorted((float(s) for s in scores), reverse=True)
    top1 = ordered[0]
    rest = ordered[1:]
    mean_rest = sum(rest) / len(rest)

    return round(max(0.0, top1 - mean_rest), 4)


def compute_zscore_gap(scores: List[float]) -> float:
    """
    Confidence gap normalized by the signal's own spread:
    (top1 - mean(rest)) / stdev(all scores).

    Used only to feed calculate_agtr_weights_adaptive - NOT a replacement
    for compute_confidence_gap, which stays min-max/raw-scale for the
    confidence_label UI badge (see pipeline.py).

    Why this exists: min-max-normalizing each signal and taking
    top1-vs-mean-of-rest corrects for scale but not *shape*. PageRank on
    a small graph is naturally power-law-shaped (one or two hub nodes far
    ahead of a long tail), while semantic cosine similarity clusters
    tightly. That shape mismatch made the graph signal look "confident"
    almost regardless of query, and the semantic signal look
    "unconfident" almost regardless of query - not genuine adaptivity,
    just two fixed bands colliding. Dividing by the signal's own stdev
    measures the gap in units of that signal's typical variability,
    which is far less sensitive to distribution shape than a min-max
    range (which is dominated by a single min/max outlier).
    """
    if len(scores) < 2:
        return 0.0

    ordered = sorted((float(s) for s in scores), reverse=True)
    top1 = ordered[0]
    rest = ordered[1:]
    mean_rest = sum(rest) / len(rest)

    mean_all = sum(ordered) / len(ordered)
    variance = sum((s - mean_all) ** 2 for s in ordered) / len(ordered)
    stdev = math.sqrt(variance)
    if stdev < 1e-9:
        return 0.0

    return round(max(0.0, (top1 - mean_rest) / stdev), 4)


def normalize_scores(values: List[float]) -> List[float]:
    """
    Min-max normalize to [0, 1]. The three AGTR signals live on very
    different natural scales - e.g. PageRank scores sum to 1 across all
    graph nodes and are naturally much smaller in absolute terms than
    semantic cosine similarity. Combining or gap-comparing raw values
    would let scale, not actual relevance, decide the outcome.

    A flat input (max == min) carries no discriminative information, so
    it returns all zeros rather than an arbitrary constant.
    """
    if not values:
        return []

    lo, hi = min(values), max(values)
    if hi - lo < 1e-12:
        return [0.0] * len(values)

    return [(v - lo) / (hi - lo) for v in values]


def calculate_agtr_weights_adaptive(
    Cs: float, Cg: float, Ct: float, k: float = 1.5, theta: float = 1.0
) -> Tuple[float, float, float]:
    """
    Step 2 of AGTR: adaptive multi-signal weighting. Each signal's
    confidence gap (how much it actually discriminates among the current
    candidates) is passed through a shared sigmoid, then the three raw
    weights are renormalized to sum to 1.

    Cs/Cg/Ct must all be computed the same way - compute_zscore_gap, not
    compute_confidence_gap (see pipeline.py) - so a shared (k, theta)
    threshold is comparing like with like. Defaults are calibrated for
    the z-score gap's natural range (roughly 0 = no separation, ~1 =
    modest, 3+ = a strong outlier), not the older 0-1 min-max range.
    """
    def sigmoid_conf(C: float) -> float:
        return 1.0 / (1.0 + math.exp(-k * (C - theta)))

    raw_s = sigmoid_conf(Cs)
    raw_g = sigmoid_conf(Cg)
    raw_t = sigmoid_conf(Ct)
    total = raw_s + raw_g + raw_t

    if total <= 0:
        return round(1 / 3, 4), round(1 / 3, 4), round(1 / 3, 4)

    return round(raw_s / total, 4), round(raw_g / total, 4), round(raw_t / total, 4)

def determine_adaptive_hops(C: float) -> int:
    """
    Step 3 of AGTR: Determine graph traversal hop depth dynamically based on confidence C.
    """
    if C > 0.30:
        return 1  # Clear semantic match -> restrict to 1 hop
    elif C > 0.15:
        return 2  # Moderate confidence -> 2 hops
    else:
        return 3  # Low confidence / ambiguous -> expand to 3 hops

def rank_candidates_agtr(
    all_candidates: List[Dict[str, Any]],
    ws: float,
    wg: float,
    wt: float
) -> List[Dict[str, Any]]:
    """
    Step 4 of AGTR: Compute final AGTR(v) = ws*S_norm(v) + wg*G_norm(v) + wt*T_norm(v)

    Each signal is min-max normalized across the candidate set before
    being combined - the three signals live on different natural scales
    (see normalize_scores). The original, non-normalized per-signal
    scores are still stored on each candidate for display/transparency;
    only the combination math uses normalized values.
    """
    if not all_candidates:
        return []

    s_scores = [float(c.get("semantic_score", 0.0)) for c in all_candidates]
    g_scores = [float(c.get("graph_score", 0.0)) for c in all_candidates]
    t_scores = [float(c.get("git_score", 0.0)) for c in all_candidates]

    s_norm = normalize_scores(s_scores)
    g_norm = normalize_scores(g_scores)
    t_norm = normalize_scores(t_scores)

    ranked = []
    for c, s_score, g_score, t_score, sn, gn, tn in zip(
        all_candidates, s_scores, g_scores, t_scores, s_norm, g_norm, t_norm
    ):
        agtr_score = (ws * sn) + (wg * gn) + (wt * tn)

        c_copy = dict(c)
        c_copy["agtr_score"] = round(agtr_score, 4)
        c_copy["semantic_score"] = round(s_score, 4)
        c_copy["graph_score"] = round(g_score, 4)
        c_copy["git_score"] = round(t_score, 4)

        ranked.append(c_copy)

    # Sort candidates by AGTR score descending
    ranked.sort(key=lambda x: x["agtr_score"], reverse=True)

    # Assign rank
    for idx, item in enumerate(ranked):
        item["rank"] = idx + 1

    return ranked
