"""Tests for L4 event store."""

import json
from pathlib import Path

from docs_code_drift_detector.event_store import EventStore, ToolEvent


def test_event_store_append_and_replay(tmp_path):
    store = EventStore(tmp_path, run_id="test-run")
    store.append("run.started", "lead", agent_name="lead", phase="plan")
    store.append(
        "tool.called", "worker", agent_name="doc_analyzer",
        tool_event=ToolEvent("filesystem.read", "read", "success"),
    )
    events = store.replay()
    assert len(events) == 2
    assert events[0]["event_type"] == "run.started"
    assert events[1]["tool_event"]["tool"] == "filesystem.read"
    assert (tmp_path / ".events.jsonl").exists()


def test_event_store_snapshot(tmp_path):
    store = EventStore(tmp_path, run_id="snap-run")
    store.append("run.started", "lead")
    store.save_snapshot({"drift_count": 3})
    snapshot = EventStore.load_snapshot(tmp_path / ".events.snapshot.json")
    assert snapshot["run_id"] == "snap-run"
    assert snapshot["state"]["drift_count"] == 3
