"""Post-demo human approval: Enter → GitHub PR, n → regenerate patch."""

from __future__ import annotations

import json
import shutil
from collections.abc import Callable
from pathlib import Path
from typing import Any

from docs_code_drift_detector.config import AppConfig
from docs_code_drift_detector.event_store import EventStore
from docs_code_drift_detector.fix_generator import generate_doc_patch
from docs_code_drift_detector.human_approval import (
    load_approval_gate,
    update_gate_status,
    write_approval_gate,
)
from docs_code_drift_detector.mcp.tools import github_pr_create
from docs_code_drift_detector.models import (
    DriftItem,
    DriftType,
    FixDirection,
    GovernanceDecision,
)
from docs_code_drift_detector.orchestrator import OrchestratorResult
from docs_code_drift_detector.pipeline_cycles import run_fix_qa_cycle
from docs_code_drift_detector.pr_agent import build_pr_request, get_pr_agent
from docs_code_drift_detector.provider import select_provider
from docs_code_drift_detector.spec_io import load_spec_file


def _load_report_models(report_path: Path) -> tuple[list[DriftItem], list[GovernanceDecision]]:
    data = json.loads(report_path.read_text(encoding="utf-8"))
    drifts = [
        DriftItem(
            function=d["function"],
            module=d["module"],
            drift_type=DriftType(d["drift_type"]),
            doc_value=d.get("doc_value"),
            code_value=d.get("code_value"),
            confidence=d.get("confidence", 0.0),
            evidence=d.get("evidence", {}),
            source_file=d.get("source_file", ""),
        )
        for d in data.get("drifts", [])
    ]
    decisions = [
        GovernanceDecision(
            function=d["function"],
            module=d["module"],
            direction=FixDirection(d["direction"]),
            reason=d.get("reason", ""),
            has_tests=d.get("has_tests", False),
            has_typing=d.get("has_typing", False),
            has_docstring_contract=d.get("has_docstring_contract", False),
        )
        for d in data.get("decisions", [])
    ]
    return drifts, decisions


def _append_event(out_dir: Path, run_id: str, event_type: str, payload: dict[str, Any]) -> None:
    store = EventStore(out_dir, run_id=run_id)
    store.append(event_type, "worker", agent_name="demo_interactive", phase="pr", payload=payload)


def _print_prompt(patch_path: Path) -> None:
    print("")
    print("=" * 60)
    print(" HUMAN APPROVAL")
    print("=" * 60)
    print(f" Review patch: {patch_path}")
    print("")
    print(" [Enter]  Create GitHub PR")
    print(" [n]      Regenerate patch (Fix Generator + QA)")
    print(" [q]      Quit without PR")
    print("=" * 60)
    print("> ", end="", flush=True)


def read_decision(
    *,
    input_fn: Callable[[], str] | None = None,
) -> str:
    """Return approve | revise | quit."""
    raw = (input_fn or input)().strip().lower()
    if raw in ("", "y", "yes"):
        return "approve"
    if raw in ("n", "no", "r", "revise"):
        return "revise"
    if raw in ("q", "quit"):
        return "quit"
    return "approve"


def approve_and_create_pr(
    project_root: Path,
    out_dir: Path,
    run_id: str,
    *,
    qa_passed: bool,
) -> tuple[str | None, str]:
    if not qa_passed:
        return None, "QA did not pass — regenerate patch before creating PR."

    if not shutil.which("gh"):
        return None, "gh CLI not found. Install GitHub CLI and run: gh auth login"

    report_path = out_dir / "drift_report.json"
    patch_path = out_dir / "patch.diff"
    if not patch_path.exists() or patch_path.stat().st_size == 0:
        return None, "No patch.diff to submit."

    pr_request = build_pr_request(report_path, patch_path)
    gh_result = github_pr_create(
        pr_request.title,
        pr_request.body,
        patch_path,
        hotl_approved=True,
    )
    if not gh_result.success:
        return None, gh_result.summary

    pr_url = gh_result.output.get("pr_url")
    gate = load_approval_gate(out_dir / "approval_gate.json")
    if gate:
        gate = update_gate_status(gate, "approved")
        gate.pr_url = pr_url
        write_approval_gate(out_dir / "approval_gate.json", gate)

    _append_event(out_dir, run_id, "hotl.approved", {
        "source": "demo_interactive",
        "pr_url": pr_url,
    })
    _append_event(out_dir, run_id, "pr.created", gh_result.output)
    return pr_url, gh_result.summary


def revise_patch(
    project_root: Path,
    out_dir: Path,
    run_id: str,
    *,
    revision: int,
    use_llm: bool = True,
) -> tuple[str, bool, int]:
    """Re-run Fix Generator + QA after human rejection."""
    report_path = out_dir / "drift_report.json"
    drifts, decisions = _load_report_models(report_path)
    code_specs = load_spec_file(out_dir / "code_spec.json")
    doc_specs = load_spec_file(out_dir / "doc_spec.json")

    review_path = out_dir / "review_verdict.json"
    review_approved = True
    if review_path.exists():
        verdict = json.loads(review_path.read_text(encoding="utf-8")).get("verdict", "")
        review_approved = verdict in ("approved", "human_review_required")

    cfg = AppConfig.from_env(use_llm=use_llm)
    _, llm = select_provider(
        use_llm=cfg.use_llm,
        api_key=cfg.openai_api_key,
        model=cfg.llm_model,
        cost_budget_usd=cfg.cost_budget_usd,
    )
    patch_meta: dict[str, Any] = {}

    def _make_patch(qa_retry: int, qa_error: str) -> str:
        note = f"Human requested revision #{revision}"
        if qa_error:
            note = f"{note}; QA: {qa_error[:120]}"
        return generate_doc_patch(
            project_root,
            drifts,
            decisions,
            code_specs,
            doc_specs,
            qa_retry=qa_retry + revision,
            qa_error=note,
            llm=llm,
            patch_meta=patch_meta,
        )

    fix_qa = run_fix_qa_cycle(
        project_root,
        run_id=run_id,
        max_qa_iterations=cfg.max_qa_iterations,
        review_approved=review_approved,
        make_patch=_make_patch,
    )

    patch = fix_qa.patch
    patch_path = out_dir / "patch.diff"
    patch_path.write_text(patch, encoding="utf-8")

    qa_worker = fix_qa.qa_result.to_worker_report()
    qa_worker["output"]["fix_invocations"] = fix_qa.fix_invocations
    qa_worker["output"]["human_revision"] = revision
    (out_dir / "qa_result.json").write_text(
        json.dumps(qa_worker, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    agent = get_pr_agent(create_pr=False)
    if hasattr(agent, "run_dry_run"):
        agent.run_dry_run(report_path, patch_path, output_path=out_dir / "pr_dry_run.txt")

    gate = load_approval_gate(out_dir / "approval_gate.json")
    if gate:
        gate = update_gate_status(gate, "pending")
        gate.message = f"Revision #{revision} — awaiting human approval."
        write_approval_gate(out_dir / "approval_gate.json", gate)

    _append_event(out_dir, run_id, "fix_generator.invoked", {
        "source": "demo_interactive",
        "revision": revision,
        "fix_invocations": fix_qa.fix_invocations,
    })
    _append_event(out_dir, run_id, "qa.completed", {
        "passed": fix_qa.qa_result.passed,
        "revision": revision,
    })

    return patch, fix_qa.qa_result.passed, fix_qa.fix_invocations


def run_interactive_hotl(
    result: OrchestratorResult,
    project_root: Path,
    out_dir: Path,
    *,
    use_llm: bool = True,
    input_fn: Callable[[], str] | None = None,
) -> OrchestratorResult:
    """Prompt after demo: Enter → PR, n → revise loop."""
    if result.pr_url:
        return result

    patch_path = out_dir / "patch.diff"
    revision = 0

    while True:
        _print_prompt(patch_path)
        decision = read_decision(input_fn=input_fn)

        if decision == "quit":
            print("Skipped PR creation.")
            return result

        if decision == "revise":
            revision += 1
            print(f"\nRegenerating patch (revision #{revision})...")
            _, qa_passed, invocations = revise_patch(
                project_root,
                out_dir,
                result.run_id,
                revision=revision,
                use_llm=use_llm,
            )
            result.qa_passed = qa_passed
            result.fix_invocations = invocations
            print(f"QA passed: {qa_passed}  |  fix invocations: {invocations}")
            print(f"Updated: {patch_path}")
            continue

        print("\nCreating GitHub PR...")
        pr_url, message = approve_and_create_pr(
            project_root,
            out_dir,
            result.run_id,
            qa_passed=result.qa_passed,
        )
        if pr_url:
            result.pr_url = pr_url
            print(f"PR created: {pr_url}")
            return result

        print(f"PR failed: {message}")
        print("Press [n] to revise patch, or [q] to quit.")
        retry = read_decision(input_fn=input_fn)
        if retry == "revise":
            continue
        return result
