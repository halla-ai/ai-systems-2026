"""Integration tests for CLI."""

import json
from pathlib import Path

from docs_code_drift_detector.cli import main, scan_project

FIXTURE = Path(__file__).parent / "fixtures" / "sample_project"


def test_scan_project_writes_report(tmp_path):
    result = scan_project(FIXTURE, tmp_path)
    report_path = tmp_path / "drift_report.json"
    assert report_path.exists()
    data = json.loads(report_path.read_text(encoding="utf-8"))
    assert data["drift_count"] >= 1
    assert "drifts" in data
    assert (tmp_path / "patch.diff").exists()
    assert (tmp_path / ".events.jsonl").exists()
    assert (tmp_path / "run_report.json").exists()
    assert (tmp_path / "qa_result.json").exists()
    assert result.report.functions_scanned >= 3


def test_scan_with_dry_run_pr(tmp_path, capsys):
    exit_code = main([
        "scan",
        str(FIXTURE),
        "-o",
        str(tmp_path),
        "--dry-run-pr",
    ])
    assert exit_code == 1
    assert (tmp_path / "pr_dry_run.txt").exists()
    pr_text = (tmp_path / "pr_dry_run.txt").read_text(encoding="utf-8")
    assert "DRY-RUN PR PREVIEW" in pr_text
    assert "parse_json" in pr_text
    captured = capsys.readouterr()
    assert "PR preview:" in captured.out


def test_demo_command_prints_evidence(tmp_path, capsys):
    exit_code = main([
        "demo",
        str(FIXTURE),
        "-o",
        str(tmp_path),
        "--no-interactive",
    ])
    assert exit_code == 1
    captured = capsys.readouterr()
    assert "RUN EVIDENCE" in captured.out
    assert "pipeline timeline:" in captured.out
    assert (tmp_path / "replay_summary.json").exists()
