from app.analysis.agtr import (
    compute_confidence_gap,
    compute_zscore_gap,
    normalize_scores,
    calculate_agtr_weights_adaptive,
)


def test_compute_confidence_gap_clear_winner():
    gap = compute_confidence_gap([0.9, 0.3, 0.3, 0.3])
    assert gap == 0.6


def test_compute_confidence_gap_flat_scores():
    gap = compute_confidence_gap([0.5, 0.5, 0.5, 0.5])
    assert gap == 0.0


def test_compute_confidence_gap_unsorted_input():
    # Must find the true top score regardless of input order - graph/git
    # score lists aren't guaranteed to arrive pre-sorted like semantic ones.
    gap = compute_confidence_gap([0.2, 0.9, 0.3])
    assert gap == 0.65


def test_compute_confidence_gap_empty():
    assert compute_confidence_gap([]) == 0.0


def test_compute_confidence_gap_single_score():
    assert compute_confidence_gap([0.7]) == 0.7


def test_compute_zscore_gap_clear_separation():
    # top1=10, rest=[1,1,1,1]: mean_rest=1, mean_all=2.8, stdev=3.6,
    # gap=(10-1)/3.6=2.5 - hand-verified.
    gap = compute_zscore_gap([10, 1, 1, 1, 1])
    assert abs(gap - 2.5) < 1e-6


def test_compute_zscore_gap_no_separation():
    # Identical scores: zero spread, zero gap (not a division error).
    assert compute_zscore_gap([0.5, 0.5, 0.5, 0.5]) == 0.0


def test_compute_zscore_gap_unsorted_input():
    gap_sorted = compute_zscore_gap([10, 1, 1, 1, 1])
    gap_unsorted = compute_zscore_gap([1, 1, 10, 1, 1])
    assert gap_sorted == gap_unsorted


def test_compute_zscore_gap_empty():
    assert compute_zscore_gap([]) == 0.0


def test_compute_zscore_gap_single_score():
    # Unlike compute_confidence_gap, there's no "rest" to compare against
    # with only one score, so this is 0 (no established gap), not the
    # raw score itself.
    assert compute_zscore_gap([0.7]) == 0.0


def test_normalize_scores_scales_to_unit_range():
    result = normalize_scores([0.1, 0.2, 0.3])
    expected = [0.0, 0.5, 1.0]
    assert all(abs(r - e) < 1e-9 for r, e in zip(result, expected))


def test_normalize_scores_flat_input_returns_zeros():
    # No spread means no discriminative information - represent that as
    # all-zero rather than an arbitrary constant.
    assert normalize_scores([0.5, 0.5, 0.5]) == [0.0, 0.0, 0.0]


def test_normalize_scores_empty():
    assert normalize_scores([]) == []


def test_weights_sum_to_one():
    ws, wg, wt = calculate_agtr_weights_adaptive(0.5, 0.3, 0.1)
    # Each weight is independently rounded to 4 decimals, so the sum can
    # drift slightly from exactly 1.0 - tolerance accounts for that.
    assert abs((ws + wg + wt) - 1.0) < 1e-3


def test_flat_signal_gets_least_weight():
    # Regression test for the bug that motivated this redesign: a signal
    # with zero confidence gap (e.g. temporal score flat because a
    # project has no real git history) must end up with less weight than
    # signals that actually discriminate, not a fixed ~31% share.
    ws, wg, wt = calculate_agtr_weights_adaptive(Cs=0.5, Cg=0.5, Ct=0.0)
    assert wt < ws
    assert wt < wg


def test_all_flat_confidence_gives_equal_weights():
    ws, wg, wt = calculate_agtr_weights_adaptive(0.0, 0.0, 0.0)
    assert abs(ws - 1 / 3) < 1e-3
    assert abs(wg - 1 / 3) < 1e-3
    assert abs(wt - 1 / 3) < 1e-3


def test_high_confidence_signal_dominates():
    ws, wg, wt = calculate_agtr_weights_adaptive(Cs=0.9, Cg=0.0, Ct=0.0)
    assert ws > wg
    assert ws > wt
