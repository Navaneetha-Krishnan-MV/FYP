from app.analysis.graph_expander import compute_personalized_pagerank


def test_pagerank_decays_with_distance_from_seed():
    # chain: seed - near - far - farther
    edges = [("seed", "near"), ("near", "far"), ("far", "farther")]
    scores = compute_personalized_pagerank(edges, {"seed": 1.0})
    # "near" sits between the seed and the rest of the chain and ends up
    # highest; rank still clearly decays across the remainder of the chain.
    assert scores["near"] > scores["seed"] > scores["far"] > scores["farther"]


def test_pagerank_empty_edges_returns_empty():
    assert compute_personalized_pagerank([], {"seed": 1.0}) == {}


def test_pagerank_empty_personalization_returns_empty():
    assert compute_personalized_pagerank([("a", "b")], {}) == {}


def test_pagerank_scores_sum_to_approximately_one():
    edges = [("a", "b"), ("b", "c"), ("c", "a")]
    personalization = {"a": 0.5, "b": 0.5}
    scores = compute_personalized_pagerank(edges, personalization)
    assert abs(sum(scores.values()) - 1.0) < 1e-6
