from app.analysis.git_scorer import parse_diff_hunks, hunks_overlap_range

SAMPLE_PATCH = """@@ -10,5 +12,7 @@ public class Foo {
 some context
-old line
+new line
@@ -50,2 +55,3 @@ public class Bar {
 more context
"""


def test_parse_diff_hunks_single_hunk():
    patch = "@@ -1,3 +1,4 @@\n context\n+added\n"
    assert parse_diff_hunks(patch) == [(1, 4)]


def test_parse_diff_hunks_multiple_hunks():
    assert parse_diff_hunks(SAMPLE_PATCH) == [(12, 18), (55, 57)]


def test_parse_diff_hunks_no_length_defaults_to_one_line():
    patch = "@@ -5 +8 @@\n+x\n"
    assert parse_diff_hunks(patch) == [(8, 8)]


def test_parse_diff_hunks_empty_or_malformed():
    assert parse_diff_hunks("") == []
    assert parse_diff_hunks("not a diff at all") == []


def test_hunks_overlap_range_true_when_overlapping():
    assert hunks_overlap_range([(10, 20)], 15, 25) is True


def test_hunks_overlap_range_false_when_disjoint():
    assert hunks_overlap_range([(10, 20)], 21, 30) is False


def test_hunks_overlap_range_true_when_containing():
    assert hunks_overlap_range([(1, 100)], 40, 45) is True


def test_hunks_overlap_range_no_hunks():
    assert hunks_overlap_range([], 1, 10) is False
