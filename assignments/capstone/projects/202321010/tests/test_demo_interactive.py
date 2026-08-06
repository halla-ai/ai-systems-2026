"""Tests for post-demo interactive HOTL."""

from pathlib import Path
from unittest.mock import patch

from docs_code_drift_detector.cli import main
from docs_code_drift_detector.demo_interactive import (
    approve_and_create_pr,
    read_decision,
    run_interactive_hotl,
)
from docs_code_drift_detector.human_approval import load_approval_gate, write_approval_gate
from docs_code_drift_detector.human_approval import create_approval_gate
from docs_code_drift_detector.orchestrator import OrchestratorResult
from docs_code_drift_detector.models import DriftReport

FIXTURE = Path(__file__).parent / "fixtures" / "sample_project"


def test_read_decision_mapping():
    assert read_decision(input_fn=lambda: "") == "approve"
    assert read_decision(input_fn=lambda: "n") == "revise"
    assert read_decision(input_fn=lambda: "q") == "quit"


@patch("docs_code_drift_detector.cli.run_interactive_hotl")
def test_demo_calls_interactive_by_default(mock_hotl, tmp_path, capsys):
    mock_hotl.side_effect = lambda result, *a, **k: result
    main(["demo", str(FIXTURE), "-o", str(tmp_path)])
    mock_hotl.assert_called_once()


@patch("docs_code_drift_detector.cli.run_interactive_hotl")
def test_demo_no_interactive_skips_prompt(mock_hotl, tmp_path):
    main(["demo", str(FIXTURE), "-o", str(tmp_path), "--no-interactive"])
    mock_hotl.assert_not_called()


def test_approve_and_create_pr_updates_gate(tmp_path):
    patch_path = tmp_path / "patch.diff"
    patch_path.write_text("--- a/README.md\n+++ b/README.md\n", encoding="utf-8")
    report = {
        "project_root": str(FIXTURE),
        "functions_scanned": 3,
        "drift_count": 1,
        "drifts": [{
            "function": "parse_json",
            "module": "utils",
            "drift_type": "return_type_mismatch",
            "doc_value": "dict",
            "code_value": "Any",
            "confidence": 0.9,
            "evidence": {},
        }],
        "decisions": [],
    }
    (tmp_path / "drift_report.json").write_text(
        __import__("json").dumps(report), encoding="utf-8",
    )
    gate = create_approval_gate("run-1", requires_human=True, hotl_approved=False)
    write_approval_gate(tmp_path / "approval_gate.json", gate)

    from docs_code_drift_detector.mcp.tools import ToolResult

    fake_result = ToolResult(
        "github.pr_create", True, {"pr_url": "https://github.com/o/r/pull/99"}, "ok",
    )
    with patch("docs_code_drift_detector.demo_interactive.github_pr_create", return_value=fake_result):
        with patch("docs_code_drift_detector.demo_interactive.shutil.which", return_value="/usr/bin/gh"):
            url, msg = approve_and_create_pr(FIXTURE, tmp_path, "run-1", qa_passed=True)

    assert url == "https://github.com/o/r/pull/99"
    updated = load_approval_gate(tmp_path / "approval_gate.json")
    assert updated.status == "approved"
    assert updated.pr_url == "https://github.com/o/r/pull/99"


def test_run_interactive_hotl_quit(tmp_path):
    report = DriftReport(project_root=str(FIXTURE), functions_scanned=1)
    result = OrchestratorResult(
        report=report,
        run_id="run-x",
        events_path=tmp_path / ".events.jsonl",
        snapshot_path=tmp_path / ".events.snapshot.json",
        qa_passed=True,
    )
    (tmp_path / "patch.diff").write_text("patch", encoding="utf-8")
    inputs = iter(["q"])
    out = run_interactive_hotl(
        result, FIXTURE, tmp_path,
        input_fn=lambda: next(inputs),
    )
    assert out.pr_url is None
