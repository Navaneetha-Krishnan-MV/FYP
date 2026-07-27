import math
from typing import List, Dict, Any, Tuple

def compute_retrieval_confidence(semantic_candidates: List[Dict[str, Any]]) -> float:
    """
    Step 1 of AGTR: Measure Semantic Retrieval Confidence (C)
    C = S(v1) - (1 / (K-1)) * sum(S(vi) for i=2..K)
    """
    if not semantic_candidates:
        return 0.0
    if len(semantic_candidates) == 1:
        return float(semantic_candidates[0].get("semantic_score", 0.0))

    scores = [float(c.get("semantic_score", 0.0)) for c in semantic_candidates]
    v1_score = scores[0]
    rest_scores = scores[1:]

    mean_rest = sum(rest_scores) / len(rest_scores)
    confidence_C = max(0.0, v1_score - mean_rest)

    return round(confidence_C, 4)

def calculate_agtr_weights(C: float, k: float = 10.0, theta: float = 0.15) -> Tuple[float, float, float]:
    """
    Step 2 of AGTR: Compute dynamic weights (ws, wg, wt) based on confidence C using sigmoid curve.
    """
    # Sigmoid function for semantic weight ws
    ws = 1.0 / (1.0 + math.exp(-k * (C - theta)))

    # Remaining weight distributed to graph (60%) and temporal (40%)
    remaining = 1.0 - ws
    wg = remaining * 0.60
    wt = remaining * 0.40

    return round(ws, 4), round(wg, 4), round(wt, 4)

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
    Step 4 of AGTR: Compute final AGTR(v) = ws * S(v) + wg * G(v) + wt * T(v)
    """
    ranked = []

    for c in all_candidates:
        s_score = float(c.get("semantic_score", 0.0))
        g_score = float(c.get("graph_score", 0.0))
        t_score = float(c.get("git_score", 0.0))

        agtr_score = (ws * s_score) + (wg * g_score) + (wt * t_score)

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
