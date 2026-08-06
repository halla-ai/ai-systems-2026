"""End-of-run evidence summary for live demo (one command, full story)."""

from __future__ import annotations

import json
from pathlib import Path

from docs_code_drift_detector.orchestrator import OrchestratorResult
from docs_code_drift_detector.replay_tools import load_events, summarize_run, write_replay_summary


def print_run_evidence(result: OrchestratorResult, out_dir: Path) -> Path:
    """Print rubric-friendly summary from a single scan run."""
    events = summarize_run(load_events(out_dir, result.run_id), run_id=result.run_id)
    summary_path = write_replay_summary(out_dir, run_id=result.run_id)

    qa_iters = 0
    fix_recalled = False
    qa_path = out_dir / "qa_result.json"
    if qa_path.exists():
        qa = json.loads(qa_path.read_text(encoding="utf-8"))
        iters = qa.get("output", {}).get("iterations", [])
        qa_iters = len(iters)
        fix_recalled = any(i.get("fix_generator_recalled") for i in iters)

    gate_status = "n/a"
    gate_path = out_dir / "approval_gate.json"
    if gate_path.exists():
        gate_status = json.loads(gate_path.read_text(encoding="utf-8")).get("status", "n/a")

    lines = [
        "",
        "=" * 60,
        " RUN EVIDENCE  (one scan = full pipeline)",
        "=" * 60,
        f" run_id           {result.run_id}",
        f" functions        {result.report.functions_scanned} scanned",
        f" drifts           {len(result.report.drifts)}",
        f" review           {result.review_verdict.get('verdict', 'n/a')}",
        f" qa_passed        {result.qa_passed}  (iterations={qa_iters}, fix_recall={fix_recalled})",
        f" hotl_gate        {gate_status}  (waited={result.hotl_waited}, cycles={result.hotl_cycles})",
        f" pr_url           {result.pr_url or '(dry-run or skipped)'}",
        f" events           {events.get('event_count', 0)}  "
        f"({events.get('first_event')} -> {events.get('last_event')})",
    ]
    if result.llm_meta.get("llm_used"):
        cost = result.llm_meta.get("estimated_cost_usd", 0)
        lines.append(f" llm_cost          ~${cost:.4f}")

    lines.append("")
    lines.append(" pipeline timeline:")
    key_events = {
        "run.started", "drift.detected", "governance.decided", "review.completed",
        "fix_generator.invoked", "qa.completed", "pr.dry_run", "pr.created", "pr.completed",
        "hotl.waiting", "hotl.approved", "hotl.rejected", "hotl.timeout", "run.completed",
        "run.aborted",
    }
    for item in events.get("timeline", []):
        et = item.get("event_type", "")
        if et in key_events:
            lines.append(f"   - {et}")

    lines.extend([
        "",
        " artifacts:",
        f"   {out_dir / 'drift_report.json'}",
        f"   {out_dir / 'qa_result.json'}",
        f"   {out_dir / '.events.jsonl'}",
        f"   {out_dir / 'patch.diff'}",
        f"   {summary_path}",
        "=" * 60,
    ])
    print("\n".join(lines))
    return summary_path
