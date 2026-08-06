"""Tests for replay and eval commands."""

import json
from pathlib import Path

from docs_code_drift_detector.cli import eval_command, gate_command, replay_command
from docs_code_drift_detector.eval_runner import run_repeatability_eval, score_against_expectations
from docs_code_drift_detector.human_approval import create_approval_gate, write_approval_gate
from docs_code_drift_detector.replay_tools import summarize_run, write_replay_summary

FIXTURE = Path(__file__).parent / "fixtures" / "sample_project"


def test_score_against_expectations_sample_project():
    report = json.loads(
        (Path(__file__).parent / "fixtures" / "scan_output" / "drift_report.json").read_text(encoding="utf-8")
    )
    score = score_against_expectations("sample_project", report)
    assert score["scored"] is True
    assert score["function_recall"] == 1.0
    assert score["overall_pass"] is True


def test_replay_summary_after_scan(tmp_path):
    from docs_code_drift_detector.orchestrator import run_pipeline

    run_pipeline(FIXTURE, tmp_path, dry_run_pr=True)
    summary_path = write_replay_summary(tmp_path)
    data = json.loads(summary_path.read_text(encoding="utf-8"))
    assert data["event_count"] > 0
    assert data["last_event"] == "run.completed"


def test_gate_command_updates_status(tmp_path):
    gate = create_approval_gate("r1", requires_human=True, hotl_approved=False)
    write_approval_gate(tmp_path / "approval_gate.json", gate)
    assert gate_command(tmp_path, "approved") == 0
    updated = json.loads((tmp_path / "approval_gate.json").read_text(encoding="utf-8"))
    assert updated["status"] == "approved"


def test_eval_command_three_runs(tmp_path):
    out = tmp_path / "eval"
    code = eval_command(FIXTURE, out, runs=3)
    assert code == 0
    summary = json.loads((out / "eval_summary.json").read_text(encoding="utf-8"))
    assert summary["runs"] == 3
    assert summary["repeatable"] is True
    assert len(summary["run_rows"]) == 3


def test_replay_command_prints_timeline(tmp_path, capsys):
    from docs_code_drift_detector.orchestrator import run_pipeline

    run_pipeline(FIXTURE, tmp_path, dry_run_pr=True)
    assert replay_command(tmp_path) == 0
    captured = capsys.readouterr()
    assert "Timeline:" in captured.out
    assert "run.completed" in captured.out
