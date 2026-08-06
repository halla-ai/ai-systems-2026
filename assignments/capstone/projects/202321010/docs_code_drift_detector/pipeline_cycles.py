"""Fix↔QA inner loop and Human Approval↔QA outer loop (proposal §2.3)."""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from docs_code_drift_detector.human_approval import (
    ApprovalGate,
    load_approval_gate,
    write_approval_gate,
)
from docs_code_drift_detector.qa_loop import QAResult, run_qa_loop


@dataclass
class FixQAResult:
    """Result of Fix Generator ↔ QA inner cycle."""
    patch: str
    qa_result: QAResult
    fix_invocations: int = 0
    events: list[dict[str, Any]] = field(default_factory=list)


def run_fix_qa_cycle(
    project_root: Path,
    *,
    run_id: str,
    max_qa_iterations: int,
    review_approved: bool,
    make_patch: Callable[[int, str], str],
    on_fix_invoked: Callable[[int, str, str], None] | None = None,
) -> FixQAResult:
    """
    Inner loop: Fix Generator → QA → (on fail) Fix Generator → QA … max 5.

    `make_patch(qa_retry, pytest_summary)` must call Fix Generator fully.
    """
    events: list[dict[str, Any]] = []
    fix_invocations = 0

    def _refix(qa_retry: int, pytest_summary: str) -> str:
        nonlocal fix_invocations
        fix_invocations += 1
        patch = make_patch(qa_retry, pytest_summary)
        if on_fix_invoked:
            on_fix_invoked(fix_invocations, qa_retry, pytest_summary)
        events.append({
            "type": "fix_generator.recalled",
            "invocation": fix_invocations,
            "qa_retry": qa_retry,
            "reason": pytest_summary[:200],
        })
        return patch

    initial_patch = make_patch(0, "")
    fix_invocations = 1
    if on_fix_invoked:
        on_fix_invoked(1, 0, "")

    qa_result = run_qa_loop(
        project_root,
        run_id=run_id,
        max_iterations=max_qa_iterations,
        review_approved=review_approved,
        patch_text=initial_patch,
        regenerate_patch=_refix,
    )

    return FixQAResult(
        patch=qa_result.final_patch or initial_patch,
        qa_result=qa_result,
        fix_invocations=fix_invocations,
        events=events,
    )


def run_qa_only(
    project_root: Path,
    *,
    run_id: str,
    patch_text: str,
    review_approved: bool,
    max_qa_iterations: int = 5,
) -> QAResult:
    """Re-run QA Loop only (Human Approval → QA feedback)."""
    return run_qa_loop(
        project_root,
        run_id=run_id,
        max_iterations=max_qa_iterations,
        review_approved=review_approved,
        patch_text=patch_text,
        regenerate_patch=None,
    )


@dataclass
class HotlCycleResult:
    fix_qa: FixQAResult
    qa_result: QAResult
    approval_gate: ApprovalGate
    pr_url: str | None
    hotl_cycles: int
    hotl_waited: bool = False
    hotl_timed_out: bool = False
    events: list[dict[str, Any]] = field(default_factory=list)


def wait_for_gate_resolution(
    gate_path: Path,
    *,
    timeout_sec: float,
    poll_sec: float,
    on_poll: Callable[[int, float], None] | None = None,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> ApprovalGate | None:
    """Poll approval_gate.json until approved/rejected or timeout."""
    deadline = time.monotonic() + timeout_sec
    poll_count = 0
    while time.monotonic() < deadline:
        if gate_path.exists():
            gate = load_approval_gate(gate_path)
            if gate and gate.status in ("approved", "rejected"):
                return gate
        poll_count += 1
        if on_poll:
            on_poll(poll_count, max(0.0, deadline - time.monotonic()))
        sleep_fn(poll_sec)
    return None


def run_hotl_outer_loop(
    *,
    project_root: Path,
    run_id: str,
    max_qa_iterations: int,
    max_hotl_cycles: int,
    review_approved: bool,
    hotl_approved: bool,
    make_patch: Callable[[int, str], str],
    build_gate: Callable[[QAResult, str | None, bool], ApprovalGate],
    run_pr: Callable[[str, QAResult], str | None],
    on_event: Callable[[str, dict[str, Any]], None] | None = None,
    gate_path: Path | None = None,
    wait_hotl: bool = False,
    wait_hotl_timeout_sec: float = 300.0,
    wait_hotl_poll_sec: float = 2.0,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> HotlCycleResult:
    """
    Full cycle matching proposal diagram:

        Fix → QA ──(fail)──► Fix
        QA → PR → Human Approval ──(pending)──► QA
    """
    all_events: list[dict[str, Any]] = []

    def _emit(name: str, payload: dict[str, Any]) -> None:
        all_events.append({"type": name, **payload})
        if on_event:
            on_event(name, payload)

    def _persist_gate(g: ApprovalGate) -> None:
        if gate_path:
            write_approval_gate(gate_path, g)

    fix_qa = run_fix_qa_cycle(
        project_root,
        run_id=run_id,
        max_qa_iterations=max_qa_iterations,
        review_approved=review_approved,
        make_patch=make_patch,
        on_fix_invoked=lambda inv, retry, summary: _emit(
            "fix_generator.invoked",
            {"invocation": inv, "qa_retry": retry},
        ),
    )
    all_events.extend(fix_qa.events)

    patch = fix_qa.patch
    qa_result = fix_qa.qa_result
    pr_url = run_pr(patch, qa_result)
    _emit("pr.completed", {"pr_url": pr_url})

    gate = build_gate(qa_result, pr_url, hotl_approved)
    _persist_gate(gate)
    hotl_cycle = 1
    hotl_waited = False
    hotl_timed_out = False

    def _read_external_gate() -> ApprovalGate | None:
        if gate_path and gate_path.exists():
            return load_approval_gate(gate_path)
        return None

    if gate.status == "pending" and wait_hotl and not hotl_approved and gate_path:
        hotl_waited = True
        _emit("hotl.waiting", {
            "gate_file": str(gate_path),
            "timeout_sec": wait_hotl_timeout_sec,
            "poll_sec": wait_hotl_poll_sec,
            "message": (
                "Blocking until approval_gate.json is approved or rejected. "
                "In another terminal: python -m docs_code_drift_detector gate -o <output> approved"
            ),
        })

        def _on_poll(poll_count: int, remaining_sec: float) -> None:
            _emit("hotl.poll", {
                "poll": poll_count,
                "remaining_sec": round(remaining_sec, 1),
                "gate_file": str(gate_path),
            })

        resolved = wait_for_gate_resolution(
            gate_path,
            timeout_sec=wait_hotl_timeout_sec,
            poll_sec=wait_hotl_poll_sec,
            on_poll=_on_poll,
            sleep_fn=sleep_fn,
        )
        if resolved is None:
            hotl_timed_out = True
            _emit("hotl.timeout", {
                "timeout_sec": wait_hotl_timeout_sec,
                "gate_file": str(gate_path),
                "message": "HOTL wait timed out; gate still pending.",
            })
        elif resolved.status == "rejected":
            gate = resolved
            _persist_gate(gate)
            _emit("hotl.rejected", {
                "cycle": hotl_cycle,
                "source": "wait_hotl",
                "message": resolved.message,
            })
        elif resolved.status == "approved":
            qa_result = run_qa_only(
                project_root,
                run_id=run_id,
                patch_text=patch,
                review_approved=review_approved,
                max_qa_iterations=max_qa_iterations,
            )
            gate = build_gate(qa_result, pr_url, True)
            _persist_gate(gate)
            _emit("hotl.approved", {
                "cycle": hotl_cycle,
                "source": "wait_hotl",
                "qa_passed": qa_result.passed,
            })

    while (
        not wait_hotl
        and gate.status == "pending"
        and hotl_cycle < max_hotl_cycles
    ):
        external = _read_external_gate()
        if external:
            if external.status == "rejected":
                gate = external
                _emit("hotl.rejected", {
                    "cycle": hotl_cycle,
                    "source": "approval_gate.json",
                    "message": external.message,
                })
                break
            if external.status == "approved":
                gate = external
                _emit("hotl.approved", {
                    "cycle": hotl_cycle,
                    "source": "approval_gate.json",
                    "qa_passed": qa_result.passed,
                })
                break

        hotl_cycle += 1
        _emit("hotl.pending", {
            "cycle": hotl_cycle,
            "action": "rerun_qa",
            "message": "approval_gate pending — re-running QA loop",
            "gate_file": str(gate_path) if gate_path else None,
        })

        qa_result = run_qa_only(
            project_root,
            run_id=run_id,
            patch_text=patch,
            review_approved=review_approved,
            max_qa_iterations=max_qa_iterations,
        )

        if hotl_approved and qa_result.passed:
            gate = build_gate(qa_result, pr_url, True)
            _emit("hotl.approved", {"cycle": hotl_cycle, "qa_passed": True})
            break

        external = _read_external_gate()
        if external and external.status == "approved":
            gate = external
            _emit("hotl.approved", {
                "cycle": hotl_cycle,
                "source": "approval_gate.json",
                "qa_passed": qa_result.passed,
            })
            break
        if external and external.status == "rejected":
            gate = external
            _emit("hotl.rejected", {
                "cycle": hotl_cycle,
                "source": "approval_gate.json",
                "message": external.message,
            })
            break

        gate = build_gate(qa_result, pr_url, hotl_approved)
        _persist_gate(gate)

    return HotlCycleResult(
        fix_qa=fix_qa,
        qa_result=qa_result,
        approval_gate=gate,
        pr_url=pr_url,
        hotl_cycles=hotl_cycle,
        hotl_waited=hotl_waited,
        hotl_timed_out=hotl_timed_out,
        events=all_events,
    )
