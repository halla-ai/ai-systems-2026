"""Week 4 QA Loop — iterative validation with fix feedback (max 5)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from uuid import uuid4

from docs_code_drift_detector.hooks import HookResult, loop_stop_hook
from docs_code_drift_detector.mcp.tools import pytest_run
from docs_code_drift_detector.patch_applier import apply_doc_patch_to_temp
from docs_code_drift_detector.schemas import validate_required_fields


@dataclass
class QAIteration:
    iteration: int
    pytest_passed: bool
    pytest_summary: str
    review_approved: bool
    hook_result: HookResult
    fix_generator_recalled: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "iteration": self.iteration,
            "pytest_passed": self.pytest_passed,
            "pytest_summary": self.pytest_summary,
            "review_approved": self.review_approved,
            "fix_generator_recalled": self.fix_generator_recalled,
            "hook": self.hook_result.to_dict(),
        }


@dataclass
class QAResult:
    task_id: str
    run_id: str
    iterations: list[QAIteration] = field(default_factory=list)
    passed: bool = False
    stopped_reason: str = ""
    final_patch: str = ""

    def to_worker_report(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "run_id": self.run_id,
            "agent_name": "qa_agent",
            "status": "success" if self.passed else "failure",
            "output": {
                "passed": self.passed,
                "stopped_reason": self.stopped_reason,
                "iterations": [i.to_dict() for i in self.iterations],
                "final_patch_bytes": len(self.final_patch),
            },
            "artifacts": [],
            "tool_calls": [
                {
                    "tool": "pytest.run",
                    "status": "success" if i.pytest_passed else "failure",
                    "summary": i.pytest_summary,
                }
                for i in self.iterations
            ],
        }


def run_qa_loop(
    project_root: Path,
    *,
    run_id: str,
    max_iterations: int = 5,
    review_approved: bool = True,
    patch_text: str = "",
    regenerate_patch: Callable[[int, str], str] | None = None,
) -> QAResult:
    """
    QA loop: apply patch → pytest → on failure recall Fix Generator → retry (max 5).
    `regenerate_patch` must invoke Fix Generator fully (not a partial edit).
    """
    task_id = str(uuid4())
    result = QAResult(task_id=task_id, run_id=run_id)
    current_patch = patch_text

    for i in range(1, max_iterations + 1):
        qa_root = project_root
        temp_cleanup: Path | None = None
        fix_recalled = False

        if current_patch.strip():
            apply_result = apply_doc_patch_to_temp(project_root, current_patch)
            if apply_result.success and apply_result.temp_dir:
                qa_root = apply_result.temp_dir
                temp_cleanup = apply_result.temp_dir.parent

        pytest_result = pytest_run(qa_root)
        pytest_passed = pytest_result.output.get("passed", False)
        pytest_summary = pytest_result.summary

        hook = loop_stop_hook(
            i, max_iterations,
            pytest_passed=pytest_passed,
            review_approved=review_approved,
        )

        if temp_cleanup:
            import shutil
            shutil.rmtree(temp_cleanup, ignore_errors=True)

        result.iterations.append(QAIteration(
            iteration=i,
            pytest_passed=pytest_passed,
            pytest_summary=pytest_summary,
            review_approved=review_approved,
            hook_result=hook,
            fix_generator_recalled=fix_recalled,
        ))

        if hook.action == "stop":
            result.passed = pytest_passed and review_approved
            result.stopped_reason = hook.message
            result.final_patch = current_patch
            break

        # Feedback: QA fail → Fix Generator full re-call → retry
        if regenerate_patch and not pytest_passed:
            new_patch = regenerate_patch(i, pytest_summary)
            current_patch = new_patch
            result.iterations[-1].fix_generator_recalled = True
            fix_recalled = True
            continue

    if not result.final_patch:
        result.final_patch = current_patch

    errors = validate_required_fields(result.to_worker_report(), "worker_report")
    if errors:
        result.stopped_reason += f" Schema warnings: {errors}"

    return result
