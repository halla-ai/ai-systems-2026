from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
from typing import Any

from code_reviewer import CodeReviewer
from qa_agent import QAAgent
from qa_runner import TestRunner


BASE_DIR = Path(__file__).resolve().parent
REPORT_DIR = BASE_DIR / "qa_reports"
TARGET_FILE = BASE_DIR / "calculator.py"
WEEK08_PLANNER_PATH = BASE_DIR.parent.parent / "week-08" / "202121014" / "planner_agent.py"
PLANNER_REQUIREMENT = "divide() 함수에 ZeroDivisionError 처리와 입력 검증을 추가하라."


class CoderAgent:
    def __init__(self, target_file: Path) -> None:
        self.target_file = target_file

    def apply_plan(self, plan: dict[str, Any], iteration: int, feedback: str = "") -> None:
        _ = self.build_coder_brief(plan, feedback)
        if iteration == 1:
            content = self._iteration_one_code()
        else:
            content = self._iteration_two_code()
        self.target_file.write_text(content, encoding="utf-8")

    def build_coder_brief(self, plan: dict[str, Any], feedback: str = "") -> str:
        lines = [plan.get("description", "").strip(), "", "Planned tasks:"]
        for task in plan.get("tasks", []):
            lines.append(f"- {task['id']}: {task['description']}")
            for criterion in task.get("acceptance_criteria", []):
                lines.append(f"  * {criterion}")
        if feedback:
            lines.extend(["", f"Latest QA feedback: {feedback}"])
        return "\n".join(lines).strip()

    def _iteration_one_code(self) -> str:
        return '''"""Sample target module used by the QA pipeline."""


def divide(a: float, b: float) -> float:
    """Return the quotient without full planner requirements yet."""
    return a / b
'''

    def _iteration_two_code(self) -> str:
        return '''"""Sample target module used by the QA pipeline."""


def divide(a: float, b: float) -> float:
    """Return the quotient after validating numeric inputs."""
    if not isinstance(a, (int, float)) or not isinstance(b, (int, float)):
        raise TypeError("divide() expects numeric inputs")
    if b == 0:
        raise ZeroDivisionError("division by zero is not allowed")
    return a / b
'''


def load_week08_planner_class() -> type:
    if not WEEK08_PLANNER_PATH.exists():
        raise RuntimeError(
            f"Week 08 PlannerAgent not found at {WEEK08_PLANNER_PATH}. "
            "Check that assignments/week-08/202121014/planner_agent.py exists."
        )

    spec = importlib.util.spec_from_file_location("week08_planner_agent", WEEK08_PLANNER_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(
            f"Unable to load Week 08 PlannerAgent from {WEEK08_PLANNER_PATH}. "
            "The module spec could not be created."
        )

    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    planner_class = getattr(module, "PlannerAgent", None)
    if planner_class is None:
        raise RuntimeError(
            f"PlannerAgent class was not found in {WEEK08_PLANNER_PATH}. "
            "Verify the Week 08 implementation."
        )
    return planner_class


def run_planner(requirement: str) -> dict[str, Any]:
    planner_class = load_week08_planner_class()
    planner = planner_class(project_root=BASE_DIR)
    analysis = planner.analyze_codebase()
    plan_data = planner.plan(requirement)
    planner.sample_plan_path.write_text(json.dumps(plan_data, indent=2, ensure_ascii=False), encoding="utf-8")
    planner.generate_spec_md(plan_data)
    passed, issues = planner.validate_spec(plan_data)
    planner.validation_report_path.write_text(
        json.dumps({"passed": passed, "issues": issues}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    tiers = planner.create_task_dag(plan_data)
    return {
        "planner_connected": True,
        "analysis": analysis,
        "plan": plan_data,
        "validation": {"passed": passed, "issues": issues},
        "tiers": tiers,
    }


def build_summary(requirement: str, planner_result: dict[str, Any], reports: list[dict[str, object]]) -> dict[str, object]:
    return {
        "requirement": requirement,
        "planner_connected": planner_result["planner_connected"],
        "planner_summary": {
            "python_file_count": planner_result["analysis"]["python_file_count"],
            "task_count": len(planner_result["plan"]["tasks"]),
            "validation": planner_result["validation"],
            "tiers": planner_result["tiers"],
        },
        "artifacts": {
            "sample_plan": "sample_plan.json",
            "spec": "spec.md",
            "validation_report": "validation_report.json",
            "tasks_dir": "tasks",
        },
        "iterations": reports,
        "final_verdict": reports[-1]["verdict"] if reports else "unknown",
        "coverage_threshold_pct": 70,
    }


def main() -> None:
    coder = CoderAgent(TARGET_FILE)
    qa_agent = QAAgent(
        test_runner=TestRunner(workdir=BASE_DIR, cov_targets=["calculator"]),
        code_reviewer=CodeReviewer(workdir=BASE_DIR),
        report_dir=REPORT_DIR,
    )

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    planner_result = run_planner(PLANNER_REQUIREMENT)
    plan_data = planner_result["plan"]
    validation = planner_result["validation"]
    tiers = planner_result["tiers"]

    coder.apply_plan(plan_data, iteration=1)
    report_one = qa_agent.evaluate(iteration=1)
    report_one_path = qa_agent.save_report(report_one, REPORT_DIR / "iteration-01.json")

    coder.apply_plan(plan_data, iteration=2, feedback=report_one.feedback)
    report_two = qa_agent.evaluate(iteration=2)
    report_two_path = qa_agent.save_report(report_two, REPORT_DIR / "iteration-02.json")

    qa_agent.save_history(REPORT_DIR / "qa_history.json")

    summary_payload = build_summary(
        requirement=PLANNER_REQUIREMENT,
        planner_result=planner_result,
        reports=[
            {
                "iteration": report_one.iteration,
                "verdict": report_one.verdict,
                "feedback": report_one.feedback,
                "test_summary": report_one.test_result.to_summary(),
                "review_summary": {
                    "severity": report_one.review_result.severity,
                    "score": report_one.review_result.score,
                    "issues": report_one.review_result.issues,
                },
                "coverage_pct": report_one.test_result.coverage_pct,
                "report_file": report_one_path.name,
            },
            {
                "iteration": report_two.iteration,
                "verdict": report_two.verdict,
                "feedback": report_two.feedback,
                "test_summary": report_two.test_result.to_summary(),
                "review_summary": {
                    "severity": report_two.review_result.severity,
                    "score": report_two.review_result.score,
                    "issues": report_two.review_result.issues,
                },
                "coverage_pct": report_two.test_result.coverage_pct,
                "report_file": report_two_path.name,
            },
        ],
    )
    (REPORT_DIR / "pipeline-summary.json").write_text(
        json.dumps(summary_payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    ordered_tiers = ", ".join(f"{task_id}:{tier}" for task_id, tier in sorted(tiers.items()))
    print(f"Planner connected: {planner_result['planner_connected']}")
    print(f"Generated tasks: {len(plan_data['tasks'])}")
    print(f"Validation passed: {validation['passed']}")
    print(f"Validation issues: {validation['issues']}")
    print(f"Task tiers: {ordered_tiers}")
    print(f"Iteration 1 verdict: {report_one.verdict}")
    print(f"Iteration 2 verdict: {report_two.verdict}")
    print(f"Final verdict: {summary_payload['final_verdict']}")
    print(json.dumps(summary_payload, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
