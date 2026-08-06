from code_reviewer import ReviewResult
from qa_agent import QAAgent
from qa_runner import TestResult


def build_result(*, failed: int = 0, errors: int = 0, coverage: float | None = 90.0) -> TestResult:
    return TestResult(
        passed=2,
        failed=failed,
        errors=errors,
        duration_sec=0.2,
        coverage_pct=coverage,
        failed_tests=["tests/test_example.py::test_failure"] if failed or errors else [],
        full_output="pytest output",
    )


def test_decide_requests_changes_for_test_failures() -> None:
    agent = QAAgent()
    verdict, feedback = agent._decide(build_result(failed=1), ReviewResult("pass", [], [], 100))
    assert verdict == "request_changes"
    assert "Tests are failing" in feedback


def test_decide_rejects_blocking_review() -> None:
    agent = QAAgent()
    verdict, _ = agent._decide(build_result(), ReviewResult("block", ["danger"], [], 20))
    assert verdict == "reject"


def test_decide_requests_changes_for_low_coverage() -> None:
    agent = QAAgent()
    verdict, _ = agent._decide(build_result(coverage=65.0), ReviewResult("pass", [], [], 100))
    assert verdict == "request_changes"


def test_decide_approves_warn_review() -> None:
    agent = QAAgent()
    verdict, feedback = agent._decide(build_result(), ReviewResult("warn", ["debug print"], [], 80))
    assert verdict == "approve"
    assert "warnings" in feedback

