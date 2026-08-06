from __future__ import annotations

import ast
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class TaskNode:
    id: str
    description: str
    target_files: list[str]
    dependencies: list[str]
    acceptance_criteria: list[str]
    assumptions: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "description": self.description,
            "target_files": self.target_files,
            "dependencies": self.dependencies,
            "acceptance_criteria": self.acceptance_criteria,
            "assumptions": self.assumptions,
        }


class PlannerAgent:
    def __init__(self, project_root: Path | str | None = None) -> None:
        self.project_root = Path(project_root or Path(__file__).resolve().parent)
        self.tasks_dir = self.project_root / "tasks"
        self.sample_plan_path = self.project_root / "sample_plan.json"
        self.spec_path = self.project_root / "spec.md"
        self.validation_report_path = self.project_root / "validation_report.json"

    def analyze_codebase(self) -> dict[str, Any]:
        py_files = sorted(self.project_root.rglob("*.py"))
        file_summaries = [self.analyze_functions(path) for path in py_files]
        imports = sorted({item for summary in file_summaries for item in summary["imports"]})

        return {
            "project_root": str(self.project_root),
            "python_file_count": len(py_files),
            "python_files": [str(path.relative_to(self.project_root)).replace("\\", "/") for path in py_files],
            "directory_structure": self.analyze_structure(),
            "imports": imports,
            "files": file_summaries,
        }

    def analyze_structure(self) -> dict[str, Any]:
        def walk(path: Path) -> dict[str, Any]:
            entry: dict[str, Any] = {
                "type": "directory",
                "is_package": (path / "__init__.py").exists(),
                "children": {},
            }
            for child in sorted(path.iterdir(), key=lambda item: (item.is_file(), item.name.lower())):
                if child.name in {".git", "__pycache__", ".pytest_cache"}:
                    continue
                if child.is_dir():
                    entry["children"][child.name] = walk(child)
                else:
                    entry["children"][child.name] = {
                        "type": "file",
                        "module": child.suffix == ".py",
                    }
            return entry

        return walk(self.project_root)

    def analyze_functions(self, file_path: Path) -> dict[str, Any]:
        source = file_path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(file_path))

        functions: list[str] = []
        classes: list[str] = []
        imports: list[str] = []

        for node in tree.body:
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                imports.extend(self._format_import(node))
            elif isinstance(node, ast.FunctionDef):
                functions.append(self._format_signature(node))
            elif isinstance(node, ast.AsyncFunctionDef):
                functions.append(f"async {self._format_signature(node)}")
            elif isinstance(node, ast.ClassDef):
                classes.append(node.name)

        return {
            "file": str(file_path.relative_to(self.project_root)).replace("\\", "/"),
            "functions": functions,
            "classes": classes,
            "imports": imports,
        }

    def plan(self, requirement: str) -> dict[str, Any]:
        analysis = self.analyze_codebase()
        calculator_summary = next(
            (item for item in analysis["files"] if item["file"] == "calculator.py"),
            {"file": "calculator.py", "functions": [], "classes": [], "imports": []},
        )

        tasks = [
            TaskNode(
                id="task-001",
                description="Analyze the current calculator divide() behavior and clarify the requirement for zero division and invalid input handling.",
                target_files=["calculator.py", "spec.md"],
                dependencies=[],
                acceptance_criteria=[
                    "The current divide(a, b) signature and behavior are documented from the analyzed codebase.",
                    "The spec explicitly distinguishes ZeroDivisionError handling from non-numeric input validation.",
                ],
                assumptions=[
                    "calculator.py is the primary implementation file for the divide() feature.",
                    "Input validation means rejecting unsupported argument types before division is attempted.",
                ],
            ),
            TaskNode(
                id="task-002",
                description="Define the implementation-ready spec for divide() updates, expected errors, and validation rules.",
                target_files=["spec.md", "sample_plan.json"],
                dependencies=["task-001"],
                acceptance_criteria=[
                    "The spec lists at least one behavior for zero input and one behavior for invalid argument types.",
                    "The spec includes out_of_scope items so downstream implementation work stays bounded.",
                ],
                assumptions=[
                    "The architect or coder phase will use this spec as the source of truth for implementation.",
                    "The requirement does not ask for CLI changes or additional math operations.",
                ],
            ),
            TaskNode(
                id="task-003",
                description="Create a dependency-aware execution plan and task DAG for implementation, testing, and review.",
                target_files=["tasks/task-001.md", "tasks/task-002.md", "tasks/task-003.md"],
                dependencies=["task-002"],
                acceptance_criteria=[
                    "Each task file includes dependencies, tier, description, and checkbox acceptance criteria.",
                    "The DAG orders planning before implementation and implementation before validation.",
                ],
                assumptions=[
                    "Three tasks are sufficient for this planning demo.",
                    "Validation and testing can be described as planned work even if not implemented in this assignment.",
                ],
            ),
        ]

        return {
            "title": "PlannerAgent plan for calculator divide() hardening",
            "description": (
                "Generate a planning artifact set for updating divide() with ZeroDivisionError handling and input "
                "validation based on the local calculator codebase analysis."
            ),
            "requirement": requirement,
            "codebase_summary": {
                "python_file_count": analysis["python_file_count"],
                "python_files": analysis["python_files"],
                "calculator_analysis": calculator_summary,
            },
            "tasks": [task.to_dict() for task in tasks],
            "out_of_scope": [
                "Implementing the actual divide() code change in calculator.py.",
                "Adding a CLI, web UI, or packaging changes.",
                "Refactoring unrelated calculator functions such as add() or fibonacci().",
            ],
        }

    def generate_spec_md(self, plan_data: dict[str, Any]) -> str:
        lines = [
            "# Planning Spec",
            "",
            "## Project Overview",
            "",
            plan_data["description"],
            "",
            f"- Requirement: {plan_data['requirement']}",
            f"- Primary target: `calculator.py`",
            "",
            "## Task List",
            "",
        ]

        for task in plan_data["tasks"]:
            lines.extend(
                [
                    f"### {task['id']}: {task['description']}",
                    "",
                    f"- Target files: {', '.join(f'`{item}`' for item in task['target_files'])}",
                    f"- Dependencies: {', '.join(task['dependencies']) if task['dependencies'] else 'None'}",
                    "",
                    "#### Acceptance Criteria",
                    "",
                ]
            )
            for item in task["acceptance_criteria"]:
                lines.append(f"- {item}")
            lines.extend(["", "#### Assumptions", ""])
            for item in task["assumptions"]:
                lines.append(f"- {item}")
            lines.append("")

        lines.extend(["## Out of Scope", ""])
        for item in plan_data["out_of_scope"]:
            lines.append(f"- {item}")
        lines.append("")

        spec_text = "\n".join(lines)
        self.spec_path.write_text(spec_text, encoding="utf-8")
        return spec_text

    def validate_spec(self, plan_data: dict[str, Any]) -> tuple[bool, list[str]]:
        issues: list[str] = []

        tasks = plan_data.get("tasks", [])
        if not plan_data.get("out_of_scope"):
            issues.append("out_of_scope must not be empty.")

        for task in tasks:
            acceptance = task.get("acceptance_criteria", [])
            assumptions = task.get("assumptions", [])
            if not acceptance:
                issues.append(f"{task.get('id', 'unknown')} is missing acceptance_criteria.")
            elif len(acceptance) < 2:
                issues.append(f"{task.get('id', 'unknown')} must have at least 2 acceptance_criteria.")
            if not assumptions:
                issues.append(f"{task.get('id', 'unknown')} is missing assumptions.")

        return len(issues) == 0, issues

    def create_task_dag(self, plan_data: dict[str, Any]) -> dict[str, int]:
        self.tasks_dir.mkdir(parents=True, exist_ok=True)
        tasks = {task["id"]: task for task in plan_data["tasks"]}
        tiers: dict[str, int] = {}

        def resolve_tier(task_id: str) -> int:
            if task_id in tiers:
                return tiers[task_id]
            dependencies = tasks[task_id]["dependencies"]
            if not dependencies:
                tiers[task_id] = 1
            else:
                tiers[task_id] = max(resolve_tier(dep_id) for dep_id in dependencies) + 1
            return tiers[task_id]

        for task_id in tasks:
            resolve_tier(task_id)

        for task_id, task in tasks.items():
            markdown = [
                "---",
                f"id: {task_id}",
                f"tier: {tiers[task_id]}",
                f"dependencies: {json.dumps(task['dependencies'])}",
                "---",
                "",
                "## Description",
                "",
                task["description"],
                "",
                "### Acceptance Criteria",
                "",
            ]
            for criterion in task["acceptance_criteria"]:
                markdown.append(f"* [ ] {criterion}")
            markdown.extend(["", "### Assumptions", ""])
            for assumption in task["assumptions"]:
                markdown.append(f"- {assumption}")

            task_path = self.tasks_dir / f"{task_id}.md"
            task_path.write_text("\n".join(markdown) + "\n", encoding="utf-8")

        return tiers

    def run(self, requirement: str) -> dict[str, Any]:
        analysis = self.analyze_codebase()
        plan_data = self.plan(requirement)
        self.sample_plan_path.write_text(json.dumps(plan_data, indent=2), encoding="utf-8")
        self.generate_spec_md(plan_data)
        passed, issues = self.validate_spec(plan_data)
        self.validation_report_path.write_text(
            json.dumps({"passed": passed, "issues": issues}, indent=2),
            encoding="utf-8",
        )
        tiers = self.create_task_dag(plan_data)

        return {
            "analysis": analysis,
            "plan": plan_data,
            "validation": {"passed": passed, "issues": issues},
            "tiers": tiers,
        }

    def _format_import(self, node: ast.AST) -> list[str]:
        if isinstance(node, ast.Import):
            return [alias.name for alias in node.names]
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            return [f"{module}:{alias.name}" for alias in node.names]
        return []

    def _format_signature(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
        positional = [arg.arg for arg in node.args.args]
        kwonly = [arg.arg for arg in node.args.kwonlyargs]
        args = positional.copy()
        if node.args.vararg:
            args.append(f"*{node.args.vararg.arg}")
        args.extend(kwonly)
        if node.args.kwarg:
            args.append(f"**{node.args.kwarg.arg}")
        return f"{node.name}({', '.join(args)})"


def main() -> None:
    requirement = "divide() 함수에 ZeroDivisionError 처리와 입력 검증을 추가하라."
    agent = PlannerAgent()
    result = agent.run(requirement)

    analysis = result["analysis"]
    plan_data = result["plan"]
    validation = result["validation"]
    tiers = result["tiers"]

    ordered_tiers = ", ".join(f"{task_id}:{tier}" for task_id, tier in sorted(tiers.items()))

    print(f"Analyzed Python files: {analysis['python_file_count']}")
    print(f"Generated tasks: {len(plan_data['tasks'])}")
    print(f"Validation passed: {validation['passed']}")
    print(f"Validation issues: {validation['issues']}")
    print(f"Task tiers: {ordered_tiers}")


if __name__ == "__main__":
    main()

