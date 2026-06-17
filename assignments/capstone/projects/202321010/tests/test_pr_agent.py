"""Tests for PR agent dry-run."""

import json
from pathlib import Path

from docs_code_drift_detector.pr_agent import (
    StubPRAgent,
    build_pr_request,
    generate_pr_body,
    generate_pr_title,
    load_drift_report,
)

FIXTURE = Path(__file__).parent / "fixtures" / "scan_output"
REPORT_PATH = FIXTURE / "drift_report.json"
PATCH_PATH = FIXTURE / "patch.diff"


def test_load_drift_report():
    report = load_drift_report(REPORT_PATH)
    assert report["drift_count"] >= 1
    assert "drifts" in report


def test_generate_pr_title():
    report = load_drift_report(REPORT_PATH)
    title = generate_pr_title(report)
    assert "documentation drift" in title
    assert "sample_project" in title


def test_generate_pr_body_includes_drifts():
    report = load_drift_report(REPORT_PATH)
    body = generate_pr_body(report, PATCH_PATH)
    assert "parse_json" in body
    assert "return_structure_mismatch" in body
    assert "Governance decisions" in body
    assert "Structural drifts" in body or "Detected drifts" in body or "parse_json" in body


def test_generate_pr_body_semantic_hitl_section():
    report = {
        "functions_scanned": 1,
        "drift_count": 1,
        "drifts": [{
            "function": "to_upper",
            "module": "utils",
            "drift_type": "semantic_mismatch",
            "doc_value": "uppercase",
            "code_value": "calls lower()",
            "confidence": 0.9,
            "evidence": {"reason": "doc vs code"},
        }],
        "decisions": [],
        "code_suggestions": [],
    }
    body = generate_pr_body(report, PATCH_PATH)
    assert "Semantic mismatch candidates (HITL" in body
    assert "no auto-fix" in body
    assert "to_upper" in body


def test_build_pr_request():
    request = build_pr_request(REPORT_PATH, PATCH_PATH)
    assert request.title
    assert request.body
    assert request.patch_path == PATCH_PATH


def test_stub_pr_agent_dry_run_create_pr():
    agent = StubPRAgent()
    request = build_pr_request(REPORT_PATH, PATCH_PATH)
    result = agent.create_pr(request)
    assert result.success is True
    assert result.dry_run is True
    assert result.pr_url is None
    assert "DRY-RUN PR PREVIEW" in result.message
    assert request.title in result.message


def test_stub_pr_agent_generate_dry_run():
    agent = StubPRAgent()
    content = agent.generate_dry_run(REPORT_PATH, PATCH_PATH)
    assert "sample_project" in content.title
    assert "parse_json" in content.body
    output = content.format_output()
    assert "DRY-RUN PR PREVIEW" in output
    assert "--create-pr" in output


def test_stub_pr_agent_run_dry_run_saves_file(tmp_path):
    agent = StubPRAgent()
    out_file = tmp_path / "pr_dry_run.txt"
    content = agent.run_dry_run(REPORT_PATH, PATCH_PATH, output_path=out_file)
    assert out_file.exists()
    saved = out_file.read_text(encoding="utf-8")
    assert content.title in saved
    assert "DRY-RUN PR PREVIEW" in saved


def test_generate_pr_title_no_drift(tmp_path):
    report = {
        "project_root": str(tmp_path / "myapp"),
        "drift_count": 0,
        "drifts": [],
    }
    title = generate_pr_title(report)
    assert "no documentation drift" in title
