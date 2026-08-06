"""Multi-agent orchestrator — Week 1/7 pipeline with L3–L7 integration."""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from uuid import uuid4

from docs_code_drift_detector.code_analyzer import analyze_file
from docs_code_drift_detector.collaboration import (
    CollaborationSession,
    CollaborationState,
    new_task_id,
)
from docs_code_drift_detector.doc_analyzer import analyze_docs
from docs_code_drift_detector.drift_detector import detect_drift
from docs_code_drift_detector.event_store import EventStore, ToolEvent
from docs_code_drift_detector.fix_generator import (
    generate_code_suggestions,
    generate_doc_patch,
)
from docs_code_drift_detector.pipeline_cycles import run_hotl_outer_loop
from docs_code_drift_detector.human_approval import (
    ApprovalGate,
    build_hotl_comment,
    create_approval_gate,
    post_pr_review_comment,
    write_approval_gate,
)
from docs_code_drift_detector.llm_drift_reviewer import review_drifts_with_llm
from docs_code_drift_detector.llm_semantic_detector import detect_semantic_drifts
from docs_code_drift_detector.runtime_verifier import enrich_specs_with_runtime
from docs_code_drift_detector.spec_io import write_code_spec, write_doc_spec
from docs_code_drift_detector.governance import apply_governance
from docs_code_drift_detector.hooks import blocking_hooks, run_all_hooks
from docs_code_drift_detector.config import AppConfig
from docs_code_drift_detector.llm_doc_parser import enhance_doc_specs_with_llm
from docs_code_drift_detector.mcp.tools import (
    filesystem_read,
    github_pr_create,
    github_pr_create_dry_run,
)
from docs_code_drift_detector.models import DriftReport, FixDirection, FunctionSpec
from docs_code_drift_detector.provider import select_provider
from docs_code_drift_detector.pr_agent import build_pr_request, get_pr_agent
from docs_code_drift_detector.schemas import validate_required_fields
from docs_code_drift_detector.skill_runtime import load_all_skills


@dataclass
class OrchestratorResult:
    report: DriftReport
    run_id: str
    events_path: Path
    snapshot_path: Path
    qa_passed: bool
    hook_results: list[dict[str, Any]] = field(default_factory=list)
    collaboration: dict[str, Any] = field(default_factory=dict)
    worker_reports: list[dict[str, Any]] = field(default_factory=list)
    review_verdict: dict[str, Any] = field(default_factory=dict)
    provider_profile: str = ""
    llm_meta: dict[str, Any] = field(default_factory=dict)
    pr_url: str | None = None
    qa_result_path: Path | None = None
    doc_spec_path: Path | None = None
    code_spec_path: Path | None = None
    approval_gate_path: Path | None = None
    fix_invocations: int = 0
    hotl_cycles: int = 0
    hotl_waited: bool = False
    hotl_timed_out: bool = False

    def to_run_report(self) -> dict[str, Any]:
        base = self.report.to_dict()
        base.update({
            "run_id": self.run_id,
            "qa_passed": self.qa_passed,
            "qa_iterations": len(self.worker_reports[-1].get("output", {}).get("iterations", []))
            if self.worker_reports else 0,
            "collaboration_trace": self.collaboration.get("traces", []),
            "provider_profile": self.provider_profile,
            "hook_results": self.hook_results,
            "review_verdict": self.review_verdict,
            "llm_meta": self.llm_meta,
            "pr_url": self.pr_url,
            "doc_spec_path": str(self.doc_spec_path) if self.doc_spec_path else None,
            "code_spec_path": str(self.code_spec_path) if self.code_spec_path else None,
            "approval_gate_path": str(self.approval_gate_path) if self.approval_gate_path else None,
            "fix_invocations": self.fix_invocations,
            "hotl_cycles": self.hotl_cycles,
            "hotl_waited": self.hotl_waited,
            "hotl_timed_out": self.hotl_timed_out,
        })
        return base


def _function_level_code_specs(project_root: Path) -> list[FunctionSpec]:
    """Week 5 — function-level context: analyze each file's functions separately."""
    specs: list[FunctionSpec] = []
    for path in sorted(project_root.rglob("*.py")):
        try:
            rel = path.relative_to(project_root)
        except ValueError:
            continue
        if rel.parts and rel.parts[0] in {"tests", "test", ".venv", "venv"}:
            continue
        specs.extend(analyze_file(path, project_root))
    return specs


def _build_review_verdict(
    task_id: str,
    run_id: str,
    decisions: list,
    hook_results: list,
) -> dict[str, Any]:
    human_needed = any(d.direction == FixDirection.HUMAN_REVIEW for d in decisions)
    hooks_failed = any(not h["passed"] for h in hook_results)

    if human_needed:
        verdict = "human_review_required"
    elif hooks_failed:
        verdict = "escalate"
    else:
        verdict = "approved"

    review = {
        "task_id": task_id,
        "run_id": run_id,
        "reviewer_role": "reviewer",
        "verdict": verdict,
        "rubric_scores": {
            "doc_patch_safety": 1.0 if not hooks_failed else 0.0,
            "governance_applied": 1.0,
        },
        "comments": "Automated reviewer verdict based on governance + hooks.",
        "requires_hotl": human_needed,
    }
    return review


def run_pipeline(
    project_root: Path,
    output_dir: Path | None = None,
    *,
    dry_run_pr: bool = False,
    create_pr: bool = False,
    use_llm: bool = False,
    detect_semantic: bool = False,
    max_qa_iterations: int = 5,
    max_hotl_cycles: int = 5,
    hotl_approved: bool = False,
    config: AppConfig | None = None,
    on_progress: Callable[[str], None] | None = None,
) -> OrchestratorResult:
    """Execute full multi-agent pipeline with event store and collaboration."""
    project_root = project_root.resolve()
    out = output_dir or project_root
    out.mkdir(parents=True, exist_ok=True)

    def _progress(msg: str) -> None:
        if on_progress:
            on_progress(msg)

    cfg = config or AppConfig.from_env(
        use_llm=use_llm,
        detect_semantic=detect_semantic,
        create_pr=create_pr,
        dry_run_pr=dry_run_pr,
        hotl_approved=hotl_approved,
        max_qa_iterations=max_qa_iterations,
        max_hotl_cycles=max_hotl_cycles,
    )
    provider_profile, llm = select_provider(
        use_llm=cfg.use_llm,
        api_key=cfg.openai_api_key,
        model=cfg.llm_model,
        cost_budget_usd=cfg.cost_budget_usd,
    )
    llm_meta: dict[str, Any] = {"enabled": cfg.use_llm, "provider": provider_profile.name}
    run_id = str(uuid4())
    events = EventStore(out, run_id=run_id)
    session = CollaborationSession(run_id=run_id)
    skills = load_all_skills()
    worker_reports: list[dict[str, Any]] = []

    # --- Lead: initiate run ---
    lead_task = new_task_id()
    session.transition(lead_task, "lead", CollaborationState.IN_PROGRESS, "Run initiated")
    events.append("run.started", "lead", agent_name="lead", phase="plan",
                  payload={"project_root": str(project_root), "skills_loaded": list(skills.keys())})
    _progress("Analyzing documentation and source code...")

    # --- Planner: create work plan ---
    plan_task = new_task_id()
    plan_packet = {
        "task_id": plan_task,
        "run_id": run_id,
        "project_root": str(project_root),
        "phase": "plan",
        "assigned_role": "planner",
        "agent_name": "planner",
        "payload": {
            "workers": ["doc_analyzer", "code_analyzer", "drift_detector",
                        "fix_generator", "qa_agent", "pr_agent"],
            "scope": "type_and_parameter_drift_only",
            "exclude": [] if cfg.detect_semantic else ["semantic_mismatch"],
            "semantic_mode": "hitl_candidates_only" if cfg.detect_semantic else "disabled",
            "code_auto_fix_excluded": True,
        },
    }
    events.append("plan.created", "planner", agent_name="planner", phase="plan", payload=plan_packet)

    # --- Worker: doc_analyzer ---
    doc_task = new_task_id()
    readme_result = filesystem_read(project_root / "README.md")
    events.append(
        "tool.called", "worker", agent_name="doc_analyzer", phase="work",
        tool_event=ToolEvent("filesystem.read", "read", "success", str(project_root / "README.md")),
    )
    code_specs = _function_level_code_specs(project_root)
    code_specs, runtime_log = enrich_specs_with_runtime(project_root, code_specs)
    doc_specs = analyze_docs(project_root, code_specs, include_api_docs=True)
    if cfg.use_llm and readme_result.output.get("content"):
        _progress("LLM: refining doc specs...")
        doc_specs, llm_enhance = enhance_doc_specs_with_llm(
            readme_result.output["content"], doc_specs, llm,
        )
        llm_meta.update(llm_enhance)
        if llm_enhance.get("llm_used"):
            events.append(
                "tool.called", "worker", agent_name="doc_analyzer", phase="work",
                tool_event=ToolEvent("llm.complete", "doc_parse", "success"),
            )
    doc_spec_path = write_doc_spec(out / "doc_spec.json", doc_specs, str(project_root))
    code_spec_path = write_code_spec(out / "code_spec.json", code_specs, str(project_root))

    doc_report = {
        "task_id": doc_task, "run_id": run_id, "agent_name": "doc_analyzer",
        "status": "success",
        "output": {"doc_spec_count": len(doc_specs), "llm_meta": llm_meta},
        "artifacts": ["README.md", "doc_spec.json"],
        "tool_calls": [{"tool": "filesystem.read", "status": "success", "summary": readme_result.summary}],
    }
    worker_reports.append(doc_report)
    events.append("worker.completed", "worker", agent_name="doc_analyzer", phase="work", payload=doc_report)
    session.transition(doc_task, "doc_analyzer", CollaborationState.WORKER_DONE, "Doc specs extracted")

    # --- Worker: code_analyzer (Week 5 function-level) ---
    code_task = new_task_id()
    code_report = {
        "task_id": code_task, "run_id": run_id, "agent_name": "code_analyzer",
        "status": "success",
        "output": {
            "code_spec_count": len(code_specs),
            "context_mode": "function_level",
            "runtime_verification": runtime_log,
            "functions": [f"{s.module}.{s.name}" for s in code_specs],
        },
        "artifacts": ["code_spec.json"],
        "tool_calls": [],
    }
    worker_reports.append(code_report)
    events.append("worker.completed", "worker", agent_name="code_analyzer", phase="work", payload=code_report)

    # --- Worker: drift_detector ---
    drift_task = new_task_id()
    _progress("Detecting drift...")
    drifts = detect_drift(doc_specs, code_specs)
    if cfg.use_llm:
        _progress("LLM: reviewing drift candidates...")
    drifts, drift_review_meta = review_drifts_with_llm(drifts, llm if cfg.use_llm else None)
    llm_meta["drift_review"] = drift_review_meta

    if cfg.detect_semantic:
        _progress("LLM: detecting semantic mismatch candidates...")
        semantic_drifts, semantic_meta = detect_semantic_drifts(
            project_root,
            code_specs,
            llm if cfg.use_llm else None,
        )
        drifts = drifts + semantic_drifts
        llm_meta["semantic_review"] = semantic_meta
        events.append(
            "semantic.detected", "worker", agent_name="drift_detector", phase="work",
            payload={"candidate_count": semantic_meta.get("candidate_count", 0)},
        )
    drift_report_wr = {
        "task_id": drift_task, "run_id": run_id, "agent_name": "drift_detector",
        "status": "success",
        "output": {"drift_count": len(drifts)},
        "artifacts": [],
        "tool_calls": [],
    }
    worker_reports.append(drift_report_wr)
    events.append("drift.detected", "worker", agent_name="drift_detector", phase="work",
                  payload={"drift_count": len(drifts)})

    report_path = out / "drift_report.json"
    pre_report = DriftReport(
        project_root=str(project_root),
        functions_scanned=len(code_specs),
        drifts=drifts,
    )
    report_path.write_text(
        json.dumps(pre_report.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8",
    )

    # --- Governance (Week 2) ---
    decisions = apply_governance(drifts, code_specs, project_root)
    code_suggestions = generate_code_suggestions(drifts, decisions, code_specs)
    events.append("governance.decided", "worker", agent_name="governance", phase="work",
                  payload={"decision_count": len(decisions)})

    report = DriftReport(
        project_root=str(project_root),
        functions_scanned=len(code_specs),
        drifts=drifts,
        decisions=decisions,
        code_suggestions=code_suggestions,
    )
    report_path.write_text(
        json.dumps(report.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8",
    )

    session.transition(drift_task, "drift_detector", CollaborationState.UNDER_REVIEW, "Ready for review")

    # --- Reviewer (pre Fix/QA) ---
    review_task = new_task_id()
    patch_meta: dict[str, Any] = {}
    placeholder_patch = generate_doc_patch(
        project_root, drifts, decisions, code_specs, doc_specs,
        llm=llm if cfg.use_llm else None,
        patch_meta=patch_meta,
    )
    if patch_meta.get("readme_llm"):
        llm_meta["readme_write"] = patch_meta["readme_llm"]
    hook_results = run_all_hooks(
        decisions=decisions,
        patch_text=placeholder_patch,
        report_text=json.dumps(report.to_dict(), ensure_ascii=False),
        drift_count=len(drifts),
        hotl_approved=cfg.hotl_approved,
    )
    hook_dicts = [h.to_dict() for h in hook_results]
    review_verdict = _build_review_verdict(review_task, run_id, decisions, hook_dicts)
    events.append("review.completed", "reviewer", agent_name="reviewer", phase="review",
                  payload=review_verdict)

    blockers = blocking_hooks(hook_results)
    if blockers:
        review_verdict["verdict"] = "escalate"
        review_verdict["abort_reason"] = blockers[0].message
        events.append(
            "run.aborted",
            "lead",
            agent_name="lead",
            phase="review",
            payload={
                "reason": blockers[0].message,
                "hook": blockers[0].hook_name,
                "action": blockers[0].action,
            },
        )
        session.transition(review_task, "reviewer", CollaborationState.ESCALATED, blockers[0].message)
        aborted_gate = create_approval_gate(
            run_id, requires_human=False, hotl_approved=False, status="rejected",
        )
        approval_gate_path = write_approval_gate(out / "approval_gate.json", aborted_gate)
        (out / "review_verdict.json").write_text(
            json.dumps(review_verdict, indent=2, ensure_ascii=False), encoding="utf-8",
        )
        orch_result = OrchestratorResult(
            report=report,
            run_id=run_id,
            events_path=events.events_path,
            snapshot_path=events.snapshot_path,
            qa_passed=False,
            hook_results=hook_dicts,
            collaboration=session.to_dict(),
            worker_reports=worker_reports,
            review_verdict=review_verdict,
            provider_profile=provider_profile.name,
            llm_meta=llm_meta,
            approval_gate_path=approval_gate_path,
        )
        full_run_report = orch_result.to_run_report()
        events.save_snapshot(full_run_report)
        (out / "run_report.json").write_text(
            json.dumps(full_run_report, indent=2, ensure_ascii=False), encoding="utf-8",
        )
        events.append("run.completed", "lead", agent_name="lead", phase="pr",
                      payload={"drift_count": len(drifts), "qa_passed": False, "aborted": True})
        return orch_result

    # Structural doc patch may proceed when only semantic items need HITL
    review_approved = review_verdict["verdict"] in ("approved", "human_review_required")
    if review_verdict["verdict"] == "human_review_required":
        session.transition(review_task, "reviewer", CollaborationState.HUMAN_REVIEW, "HOTL required")
    elif review_verdict["verdict"] == "escalate":
        session.transition(review_task, "reviewer", CollaborationState.ESCALATED, "Hooks failed")
    else:
        session.transition(review_task, "reviewer", CollaborationState.APPROVED, "Review passed")

    patch_path = out / "patch.diff"

    def _make_patch(qa_retry: int, qa_error: str) -> str:
        meta: dict[str, Any] = {}
        patch = generate_doc_patch(
            project_root, drifts, decisions, code_specs, doc_specs,
            qa_retry=qa_retry, qa_error=qa_error,
            llm=llm if cfg.use_llm else None,
            patch_meta=meta,
        )
        if meta.get("readme_llm"):
            llm_meta["readme_write"] = meta["readme_llm"]
        return patch

    def _run_pr(patch: str, qa_result) -> str | None:
        patch_path.write_text(patch, encoding="utf-8")
        if not (cfg.dry_run_pr or cfg.create_pr):
            return None
        agent = get_pr_agent(create_pr=cfg.create_pr)
        pr_request = build_pr_request(report_path, patch_path)
        pr_task = new_task_id()

        if cfg.create_pr and review_approved and qa_result.passed:
            gh_result = github_pr_create(
                pr_request.title, pr_request.body, patch_path,
                hotl_approved=cfg.hotl_approved,
                base_branch=cfg.base_branch,
                draft=not cfg.hotl_approved,
            )
            url = gh_result.output.get("pr_url")
            if url and not cfg.hotl_approved:
                post_pr_review_comment(url, build_hotl_comment({
                    "drift_count": len(drifts),
                    "qa_passed": qa_result.passed,
                }))
            pr_report = {
                "task_id": pr_task, "run_id": run_id, "agent_name": "pr_agent",
                "status": "success" if gh_result.success else "failure",
                "output": gh_result.output,
                "artifacts": [],
                "tool_calls": [{"tool": "github.pr_create", "status": "live" if gh_result.success else "failure", "summary": gh_result.summary}],
            }
            events.append("pr.created", "worker", agent_name="pr_agent", phase="pr", payload=pr_report["output"])
            worker_reports.append(pr_report)
            return url

        gh_result = github_pr_create_dry_run(pr_request.title, pr_request.body, patch_path)
        if hasattr(agent, "run_dry_run"):
            agent.run_dry_run(report_path, patch_path, output_path=out / "pr_dry_run.txt")
        pr_report = {
            "task_id": pr_task, "run_id": run_id, "agent_name": "pr_agent",
            "status": "success",
            "output": gh_result.output,
            "artifacts": [str(out / "pr_dry_run.txt")],
            "tool_calls": [{"tool": "github.pr_create", "status": "dry_run", "summary": gh_result.summary}],
        }
        events.append("pr.dry_run", "worker", agent_name="pr_agent", phase="pr", payload=pr_report["output"])
        worker_reports.append(pr_report)
        return None

    def _build_gate(qa_result, url: str | None, approved_flag: bool) -> ApprovalGate:
        requires_human = review_verdict.get("requires_hotl", False)
        if not approved_flag and requires_human:
            return create_approval_gate(
                run_id, requires_human=True, hotl_approved=False, pr_url=url,
            )
        return create_approval_gate(
            run_id,
            requires_human=requires_human,
            hotl_approved=approved_flag,
            pr_url=url,
        )

    def _on_cycle_event(name: str, payload: dict[str, Any]) -> None:
        events.append(name, "worker", agent_name="pipeline", phase="qa", payload=payload)
        if name == "hotl.waiting":
            timeout = payload.get("timeout_sec", cfg.wait_hotl_timeout_sec)
            _progress(f"HOTL: waiting for human approval (timeout {timeout}s)...")
            _progress(f"  → python -m docs_code_drift_detector gate -o {out} approved")
        elif name == "hotl.poll":
            poll = payload.get("poll", 0)
            if poll == 1 or poll % 5 == 0:
                remaining = payload.get("remaining_sec", "?")
                _progress(f"HOTL: still waiting ({remaining}s remaining)...")
        elif name == "hotl.approved":
            _progress("HOTL: approved — re-running QA...")
        elif name == "hotl.rejected":
            _progress("HOTL: rejected — stopping.")
        elif name == "hotl.timeout":
            _progress("HOTL: timed out — gate still pending.")

    _progress("Fix generator + QA loop...")
    approval_gate_path = out / "approval_gate.json"
    if cfg.wait_hotl and not cfg.hotl_approved:
        _progress("HOTL wait enabled — pipeline will block until gate is approved/rejected.")
    hotl_result = run_hotl_outer_loop(
        project_root=project_root,
        run_id=run_id,
        max_qa_iterations=cfg.max_qa_iterations,
        max_hotl_cycles=cfg.max_hotl_cycles,
        review_approved=review_approved,
        hotl_approved=cfg.hotl_approved,
        make_patch=_make_patch,
        build_gate=_build_gate,
        run_pr=_run_pr,
        on_event=_on_cycle_event,
        gate_path=approval_gate_path,
        wait_hotl=cfg.wait_hotl,
        wait_hotl_timeout_sec=cfg.wait_hotl_timeout_sec,
        wait_hotl_poll_sec=cfg.wait_hotl_poll_sec,
    )

    patch = hotl_result.fix_qa.patch
    patch_path.write_text(patch, encoding="utf-8")
    qa_result = hotl_result.qa_result
    pr_url = hotl_result.pr_url
    approval_gate = hotl_result.approval_gate

    worker_reports.append({
        "task_id": new_task_id(), "run_id": run_id, "agent_name": "fix_generator",
        "status": "success",
        "output": {
            "patch_bytes": len(patch),
            "fix_invocations": hotl_result.fix_qa.fix_invocations,
        },
        "artifacts": [str(patch_path)],
        "tool_calls": [],
    })
    events.append("fix.generated", "worker", agent_name="fix_generator", phase="work",
                  payload={"patch_path": str(patch_path), "invocations": hotl_result.fix_qa.fix_invocations})

    qa_worker_report = qa_result.to_worker_report()
    qa_worker_report["output"]["hotl_cycles"] = hotl_result.hotl_cycles
    qa_worker_report["output"]["hotl_waited"] = hotl_result.hotl_waited
    qa_worker_report["output"]["hotl_timed_out"] = hotl_result.hotl_timed_out
    worker_reports.append(qa_worker_report)
    qa_result_path = out / "qa_result.json"
    qa_result_path.write_text(
        json.dumps(qa_worker_report, indent=2, ensure_ascii=False), encoding="utf-8",
    )
    events.append("qa.completed", "worker", agent_name="qa_agent", phase="qa",
                  payload={
                      "passed": qa_result.passed,
                      "iterations": len(qa_result.iterations),
                      "hotl_cycles": hotl_result.hotl_cycles,
                      "hotl_waited": hotl_result.hotl_waited,
                      "hotl_timed_out": hotl_result.hotl_timed_out,
                  })

    approval_gate_path = write_approval_gate(out / "approval_gate.json", approval_gate)

    orch_result = OrchestratorResult(
        report=report,
        run_id=run_id,
        events_path=events.events_path,
        snapshot_path=events.snapshot_path,
        qa_passed=qa_result.passed,
        hook_results=hook_dicts,
        collaboration=session.to_dict(),
        worker_reports=worker_reports,
        review_verdict=review_verdict,
        provider_profile=provider_profile.name,
        llm_meta=llm_meta,
        pr_url=pr_url,
        qa_result_path=qa_result_path,
        doc_spec_path=doc_spec_path,
        code_spec_path=code_spec_path,
        approval_gate_path=approval_gate_path,
        fix_invocations=hotl_result.fix_qa.fix_invocations,
        hotl_cycles=hotl_result.hotl_cycles,
        hotl_waited=hotl_result.hotl_waited,
        hotl_timed_out=hotl_result.hotl_timed_out,
    )

    full_run_report = orch_result.to_run_report()
    schema_errors = validate_required_fields(full_run_report, "run_report")
    if schema_errors:
        full_run_report["schema_warnings"] = schema_errors

    events.save_snapshot(full_run_report)
    (out / "run_report.json").write_text(
        json.dumps(full_run_report, indent=2, ensure_ascii=False), encoding="utf-8",
    )
    (out / "review_verdict.json").write_text(
        json.dumps(review_verdict, indent=2, ensure_ascii=False), encoding="utf-8",
    )

    events.append("run.completed", "lead", agent_name="lead", phase="pr",
                  payload={"drift_count": len(drifts), "qa_passed": qa_result.passed})

    return orch_result
