from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from code_reviewer import CodeReviewer, ReviewResult
from qa_runner import TestResult, TestRunner


@dataclass
class QAReport:
    iteration: int
    test_result: TestResult
    review_result: ReviewResult
    verdict: str
    feedback: str

    def to_dict(self) -> dict[str, object]:
        return {
            "iteration": self.iteration,
            "verdict": self.verdict,
            "feedback": self.feedback,
            "test_result": {
                "passed": self.test_result.passed,
                "failed": self.test_result.failed,
                "errors": self.test_result.errors,
                "duration_sec": round(self.test_result.duration_sec, 3),
                "coverage_pct": self.test_result.coverage_pct,
                "failed_tests": self.test_result.failed_tests,
                "full_output": self.test_result.full_output,
                "all_passed": self.test_result.all_passed,
                "summary": self.test_result.to_summary(),
            },
            "review_result": {
                "severity": self.review_result.severity,
                "issues": self.review_result.issues,
                "suggestions": self.review_result.suggestions,
                "score": self.review_result.score,
            },
        }


class QAAgent:
    def __init__(
        self,
        test_runner: TestRunner | None = None,
        code_reviewer: CodeReviewer | None = None,
        report_dir: Path | str | None = None,
    ) -> None:
        base_dir = Path(__file__).resolve().parent
        self.test_runner = test_runner or TestRunner(workdir=base_dir)
        self.code_reviewer = code_reviewer or CodeReviewer(workdir=base_dir)
        self.report_dir = Path(report_dir or base_dir / "qa_reports")
        self.report_dir.mkdir(parents=True, exist_ok=True)
        self.history: list[QAReport] = []

    def evaluate(self, iteration: int = 1) -> QAReport:
        test_result = self.test_runner.run()
        diff = self.code_reviewer.get_diff()
        review_result = self.code_reviewer.review_diff(diff)
        verdict, feedback = self._decide(test_result, review_result)

        report = QAReport(
            iteration=iteration,
            test_result=test_result,
            review_result=review_result,
            verdict=verdict,
            feedback=feedback,
        )
        self.history.append(report)
        return report

    def save_report(self, report: QAReport, path: Path | str) -> Path:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(report.to_dict(), indent=2), encoding="utf-8")
        return target

    def save_history(self, path: Path | str) -> Path:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        payload = {"history": [report.to_dict() for report in self.history]}
        target.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return target

    def _decide(self, test_result: TestResult, review_result: ReviewResult) -> tuple[str, str]:
        if test_result.failed > 0 or test_result.errors > 0:
            failed_list = ", ".join(test_result.failed_tests) if test_result.failed_tests else "See pytest output."
            return "request_changes", f"Tests are failing. Fix these cases first: {failed_list}"

        if review_result.should_block() or review_result.score < 40:
            issue_list = "; ".join(review_result.issues) if review_result.issues else "Blocking review issues detected."
            return "reject", f"Code review rejected the change: {issue_list}"

        if test_result.coverage_pct is not None and test_result.coverage_pct < 70:
            return (
                "request_changes",
                f"Coverage is {test_result.coverage_pct:.2f}%, below the 70% threshold.",
            )

        if review_result.severity == "warn":
            issue_list = "; ".join(review_result.issues) if review_result.issues else "Review warnings detected."
            return "approve", f"Approved with warnings: {issue_list}"

        return "approve", "All tests passed, coverage met the target, and code review found no blockers."

