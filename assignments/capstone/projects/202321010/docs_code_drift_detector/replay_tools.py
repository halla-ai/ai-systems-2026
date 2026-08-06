"""Replay and summarize event logs for observability."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from docs_code_drift_detector.event_store import EventStore


def load_events(output_dir: Path, run_id: str | None = None) -> list[dict[str, Any]]:
    store = EventStore(output_dir)
    events = store.replay()
    if run_id:
        events = [e for e in events if e.get("run_id") == run_id]
    return events


def summarize_run(events: list[dict[str, Any]], run_id: str | None = None) -> dict[str, Any]:
    if run_id:
        events = [e for e in events if e.get("run_id") == run_id]
    if not events:
        return {"run_id": run_id, "event_count": 0, "timeline": []}

    rid = run_id or events[-1].get("run_id")
    types = [e.get("event_type", "") for e in events]
    timeline = [
        {
            "timestamp": e.get("timestamp"),
            "event_type": e.get("event_type"),
            "agent_name": e.get("agent_name"),
            "phase": e.get("phase"),
        }
        for e in events
    ]
    return {
        "run_id": rid,
        "event_count": len(events),
        "first_event": events[0].get("event_type"),
        "last_event": events[-1].get("event_type"),
        "has_aborted": "run.aborted" in types,
        "has_pr_created": "pr.created" in types,
        "has_pr_dry_run": "pr.dry_run" in types,
        "hotl_pending_count": types.count("hotl.pending"),
        "hotl_rejected": "hotl.rejected" in types,
        "timeline": timeline,
    }


def load_snapshot_summary(output_dir: Path) -> dict[str, Any] | None:
    snapshot_path = output_dir / ".events.snapshot.json"
    if not snapshot_path.exists():
        return None
    data = EventStore.load_snapshot(snapshot_path)
    state = data.get("state", {})
    return {
        "run_id": data.get("run_id"),
        "event_count": data.get("event_count"),
        "qa_passed": state.get("qa_passed"),
        "drift_count": state.get("drift_count"),
        "hotl_cycles": state.get("hotl_cycles"),
        "pr_url": state.get("pr_url"),
        "llm_cost_usd": (state.get("llm_meta") or {}).get("estimated_cost_usd"),
    }


def format_replay_report(output_dir: Path, run_id: str | None = None) -> str:
    events = load_events(output_dir, run_id=run_id)
    summary = summarize_run(events, run_id=run_id)
    snapshot = load_snapshot_summary(output_dir)
    lines = [
        f"Replay: {output_dir}",
        f"Run ID: {summary.get('run_id', 'n/a')}",
        f"Events: {summary.get('event_count', 0)}",
    ]
    if snapshot:
        cost = snapshot.get("llm_cost_usd") or 0.0
        lines.append(
            f"Snapshot — drift_count={snapshot.get('drift_count')} "
            f"qa_passed={snapshot.get('qa_passed')} "
            f"cost=${cost:.4f}"
        )
    lines.append("")
    lines.append("Timeline:")
    for item in summary.get("timeline", []):
        lines.append(
            f"  {item.get('timestamp', '')}  {item.get('event_type', '')}  "
            f"({item.get('agent_name', '')}/{item.get('phase', '')})"
        )
    return "\n".join(lines)


def write_replay_summary(output_dir: Path, run_id: str | None = None) -> Path:
    events = load_events(output_dir, run_id=run_id)
    summary = summarize_run(events, run_id=run_id)
    summary["snapshot"] = load_snapshot_summary(output_dir)
    out = output_dir / "replay_summary.json"
    out.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    return out
