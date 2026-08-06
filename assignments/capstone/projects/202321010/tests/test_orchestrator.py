"""Tests for multi-agent orchestrator."""

import json
from pathlib import Path

from docs_code_drift_detector.orchestrator import run_pipeline

FIXTURE = Path(__file__).parent / "fixtures" / "sample_project"


def test_run_pipeline_produces_events_and_run_report(tmp_path):
    result = run_pipeline(FIXTURE, tmp_path, dry_run_pr=True)
    assert result.run_id
    assert result.events_path.exists()
    assert (tmp_path / "run_report.json").exists()
    assert (tmp_path / "review_verdict.json").exists()
    assert (tmp_path / "drift_report.json").exists()
    assert (tmp_path / "patch.diff").exists()
    assert (tmp_path / "doc_spec.json").exists()
    assert (tmp_path / "code_spec.json").exists()
    assert (tmp_path / "approval_gate.json").exists()
    assert (tmp_path / "pr_dry_run.txt").exists()
    assert (tmp_path / "qa_result.json").exists()
    assert len(result.report.drifts) >= 1
    assert result.provider_profile == "static-ast-v1"


def test_run_pipeline_events_replay(tmp_path):
    result = run_pipeline(FIXTURE, tmp_path)
    events = json.loads(result.events_path.read_text(encoding="utf-8").splitlines()[0])
    assert events["event_type"] == "run.started"
    replay = result.events_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(replay) >= 5


def test_run_pipeline_collaboration_trace(tmp_path):
    result = run_pipeline(FIXTURE, tmp_path)
    assert "traces" in result.collaboration
    assert len(result.collaboration["traces"]) >= 1
