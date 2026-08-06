"""Tests for human approval gate."""

from docs_code_drift_detector.human_approval import (
    create_approval_gate,
    load_approval_gate,
    update_gate_status,
    write_approval_gate,
)


def test_approval_gate_pending_without_hotl(tmp_path):
    gate = create_approval_gate("run-1", requires_human=True, hotl_approved=False)
    assert gate.status == "pending"
    assert gate.merge_blocked is True
    path = write_approval_gate(tmp_path / "approval_gate.json", gate)
    assert path.exists()


def test_gate_rejected_and_approved_transitions():
    pending = create_approval_gate("run-1", requires_human=True, hotl_approved=False)
    rejected = update_gate_status(pending, "rejected")
    assert rejected.status == "rejected"
    assert rejected.merge_blocked is True
    approved = update_gate_status(pending, "approved")
    assert approved.status == "approved"
    assert approved.hotl_approved is True


def test_load_approval_gate_roundtrip(tmp_path):
    gate = create_approval_gate("run-2", requires_human=True, hotl_approved=False)
    path = tmp_path / "approval_gate.json"
    write_approval_gate(path, gate)
    loaded = load_approval_gate(path)
    assert loaded is not None
    assert loaded.status == "pending"
