from __future__ import annotations

import json
import re
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path


@dataclass
class TestResult:
    __test__ = False

    passed: int
    failed: int
    errors: int
    duration_sec: float
    coverage_pct: float | None
    failed_tests: list[str]
    full_output: str

    @property
    def all_passed(self) -> bool:
        return self.failed == 0 and self.errors == 0

    def to_summary(self) -> dict[str, object]:
        return {
            "passed": self.passed,
            "failed": self.failed,
            "errors": self.errors,
            "duration_sec": round(self.duration_sec, 3),
            "coverage_pct": None if self.coverage_pct is None else round(self.coverage_pct, 2),
            "failed_tests": self.failed_tests,
            "all_passed": self.all_passed,
        }


class TestRunner:
    def __init__(
        self,
        workdir: Path | str | None = None,
        pytest_args: list[str] | None = None,
        cov_targets: list[str] | None = None,
        max_output_chars: int = 4000,
    ) -> None:
        self.workdir = Path(workdir or Path(__file__).resolve().parent)
        self.pytest_args = pytest_args or ["-p", "no:cacheprovider"]
        self.cov_targets = cov_targets or []
        self.max_output_chars = max_output_chars
        self.report_path = self.workdir / ".report.json"
        self.coverage_path = self.workdir / "coverage.json"

    def run(self) -> TestResult:
        self._cleanup_artifacts()
        help_text = self._get_pytest_help()
        command = [sys.executable, "-m", "pytest", "-q", *self.pytest_args]

        json_enabled = "--json-report" in help_text
        cov_enabled = "--cov" in help_text

        if json_enabled:
            command.extend(["--json-report", f"--json-report-file={self.report_path.name}"])
        if cov_enabled:
            targets = self.cov_targets or ["."]
            for target in targets:
                command.append(f"--cov={target}")
            command.append(f"--cov-report=json:{self.coverage_path.name}")

        started = time.perf_counter()
        completed = self._run_subprocess(command)
        duration_sec = time.perf_counter() - started
        output = self._merge_output(completed)

        if self._looks_like_plugin_arg_failure(completed.returncode, output):
            fallback_command = [sys.executable, "-m", "pytest", "-q", *self.pytest_args]
            started = time.perf_counter()
            completed = self._run_subprocess(fallback_command)
            duration_sec = time.perf_counter() - started
            output = self._merge_output(completed)

        return self._build_result(output=output, duration_sec=duration_sec)

    def _cleanup_artifacts(self) -> None:
        for path in (self.report_path, self.coverage_path):
            if path.exists():
                path.unlink()

    def _get_pytest_help(self) -> str:
        completed = self._run_subprocess([sys.executable, "-m", "pytest", "--help"])
        return self._merge_output(completed)

    def _run_subprocess(self, command: list[str]) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            command,
            cwd=self.workdir,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )

    def _merge_output(self, completed: subprocess.CompletedProcess[str]) -> str:
        return ((completed.stdout or "") + "\n" + (completed.stderr or "")).strip()

    def _looks_like_plugin_arg_failure(self, returncode: int, output: str) -> bool:
        if returncode == 0:
            return False
        lowered = output.lower()
        return "unrecognized arguments:" in lowered or "usage:" in lowered and "--json-report" in lowered

    def _build_result(self, output: str, duration_sec: float) -> TestResult:
        report_data = self._load_json(self.report_path)
        coverage_pct = self._load_coverage()

        if report_data is not None:
            passed, failed, errors, failed_tests = self._parse_json_report(report_data)
        else:
            passed, failed, errors, failed_tests = self._parse_text_output(output)

        return TestResult(
            passed=passed,
            failed=failed,
            errors=errors,
            duration_sec=duration_sec,
            coverage_pct=coverage_pct,
            failed_tests=failed_tests,
            full_output=self._truncate_output(output),
        )

    def _load_json(self, path: Path) -> dict[str, object] | None:
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None

    def _load_coverage(self) -> float | None:
        data = self._load_json(self.coverage_path)
        if not data:
            return None
        totals = data.get("totals", {})
        if isinstance(totals, dict):
            value = totals.get("percent_covered")
            if isinstance(value, (int, float)):
                return float(value)
        return None

    def _parse_json_report(self, report: dict[str, object]) -> tuple[int, int, int, list[str]]:
        summary = report.get("summary", {})
        tests = report.get("tests", [])
        passed = 0
        failed = 0
        errors = 0
        failed_tests: list[str] = []

        if isinstance(summary, dict):
            passed = int(summary.get("passed", 0) or 0)
            failed = int(summary.get("failed", 0) or 0)
            errors = int(summary.get("error", 0) or summary.get("errors", 0) or 0)

        if isinstance(tests, list) and tests:
            passed = sum(1 for test in tests if isinstance(test, dict) and test.get("outcome") == "passed")
            failed = sum(1 for test in tests if isinstance(test, dict) and test.get("outcome") == "failed")
            errors = sum(1 for test in tests if isinstance(test, dict) and test.get("outcome") == "error")
            failed_tests = [
                str(test.get("nodeid"))
                for test in tests
                if isinstance(test, dict) and test.get("outcome") in {"failed", "error"}
            ]

        return passed, failed, errors, failed_tests

    def _parse_text_output(self, output: str) -> tuple[int, int, int, list[str]]:
        passed = self._extract_count(output, "passed")
        failed = self._extract_count(output, "failed")
        errors = self._extract_count(output, "error") + self._extract_count(output, "errors")
        if errors == 0:
            errors = len(re.findall(r"^ERROR\s+", output, re.MULTILINE))
        failed_tests = self._extract_failed_tests(output)
        return passed, failed, errors, failed_tests

    def _extract_count(self, output: str, label: str) -> int:
        patterns = [
            rf"(\d+)\s+{label}\b",
            rf"{label}\s*=\s*(\d+)",
        ]
        for pattern in patterns:
            match = re.search(pattern, output, re.IGNORECASE)
            if match:
                return int(match.group(1))
        return 0

    def _extract_failed_tests(self, output: str) -> list[str]:
        failed_tests: list[str] = []
        pattern = re.compile(r"^(FAILED|ERROR)\s+(.+?)(?:\s+-.*)?$", re.MULTILINE)
        for _, nodeid in pattern.findall(output):
            cleaned = nodeid.strip()
            if cleaned and cleaned not in failed_tests:
                failed_tests.append(cleaned)
        return failed_tests

    def _truncate_output(self, output: str) -> str:
        if len(output) <= self.max_output_chars:
            return output
        return output[: self.max_output_chars] + "\n...[truncated]..."
