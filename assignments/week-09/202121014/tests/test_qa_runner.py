from qa_runner import TestResult


def test_all_passed_property() -> None:
    result = TestResult(
        passed=3,
        failed=0,
        errors=0,
        duration_sec=1.25,
        coverage_pct=88.5,
        failed_tests=[],
        full_output="ok",
    )
    assert result.all_passed is True


def test_to_summary_rounds_values() -> None:
    result = TestResult(
        passed=2,
        failed=1,
        errors=0,
        duration_sec=1.23456,
        coverage_pct=71.234,
        failed_tests=["tests/test_sample.py::test_case"],
        full_output="partial output",
    )
    summary = result.to_summary()
    assert summary["duration_sec"] == 1.235
    assert summary["coverage_pct"] == 71.23
    assert summary["all_passed"] is False
