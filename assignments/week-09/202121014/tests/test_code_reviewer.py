from code_reviewer import CodeReviewer


def test_review_diff_returns_pass_for_empty_diff() -> None:
    reviewer = CodeReviewer()
    result = reviewer.review_diff("")
    assert result.severity == "pass"
    assert result.score == 100


def test_fallback_reviewer_blocks_dangerous_patterns() -> None:
    reviewer = CodeReviewer()
    diff = """diff --git a/example.py b/example.py
+++ b/example.py
@@
+result = eval(user_input)
"""
    result = reviewer.review_diff(diff)
    assert result.should_block() is True
    assert result.severity == "block"


def test_fallback_reviewer_warns_for_debug_patterns() -> None:
    reviewer = CodeReviewer()
    diff = """diff --git a/example.py b/example.py
+++ b/example.py
@@
+print("debug")
"""
    result = reviewer.review_diff(diff)
    assert result.severity == "warn"
    assert result.score < 100

