"""Benchmark evaluation (proposal §4)."""

import json
from pathlib import Path

from docs_code_drift_detector.benchmark_runner import (
    BENCHMARK_PROJECT,
    PROPOSAL_SECTION4_TARGETS,
    load_ground_truth,
    run_benchmark,
    run_detection,
    score_detection,
    summarize_llm_usage,
)
from docs_code_drift_detector.cli import main

FIXTURE = Path(__file__).parent / "fixtures" / "benchmark_project"
GT = Path(__file__).parent / "fixtures" / "benchmark_ground_truth.json"


def test_ground_truth_has_30_drifts_and_10_clean():
    gt = load_ground_truth(GT)
    assert len(gt["expected_drifts"]) == 30
    assert len(gt["clean_functions"]) == 10
    cats = {r["category"] for r in gt["expected_drifts"]}
    assert "type_mismatch" in cats
    assert "parameter_mismatch" in cats
    assert "return_structure_mismatch" in cats


def test_benchmark_meets_proposal_targets(tmp_path):
    report = run_benchmark(FIXTURE, tmp_path)
    m = report["metrics"]
    assert m["functions_scanned"] == 40
    assert m["precision"] >= 0.70
    assert m["recall"] >= 0.70
    assert m["false_positive_rate"] <= 0.15
    assert m["overall_pass"] is True


def test_score_detection_counts_tp_fp_fn():
    detected, n = run_detection(FIXTURE)
    gt = load_ground_truth(GT)
    score = score_detection(detected, gt, functions_scanned=n)
    assert score["true_positives"] + score["false_negatives"] == 30
    assert score["true_positives"] + score["false_positives"] == score["detected_drifts"]


def test_realistic_sample_project_is_not_perfect():
    from docs_code_drift_detector.benchmark_runner import run_realistic_eval

    rows = run_realistic_eval()
    sp = rows["sample_project"]
    assert sp["recall"] == 1.0
    assert sp["precision"] < 1.0
    assert sp["detected_drifts"] > sp["expected_drifts"]
    assert sp["known_false_positives_hit"]


def test_summarize_llm_usage_aggregates_nested_costs():
    meta = {
        "enabled": True,
        "provider": "openai",
        "doc_parse": {"llm_used": True, "estimated_cost_usd": 0.01},
        "drift_review": {"llm_used": True, "estimated_cost_usd": 0.02},
    }
    summary = summarize_llm_usage(meta)
    assert summary["llm_used"] is True
    assert summary["estimated_cost_usd"] == 0.03


def test_proposal_section4_targets_match_ground_truth():
    gt = load_ground_truth(GT)
    assert len(gt["expected_drifts"]) == PROPOSAL_SECTION4_TARGETS["intentional_drift_functions"]
    assert len(gt["clean_functions"]) == PROPOSAL_SECTION4_TARGETS["clean_functions"]


def test_proposal_section4_full_pipeline_passes(tmp_path):
    report = run_benchmark(FIXTURE, tmp_path, full_pipeline=True)
    p4 = report["proposal_section4"]
    assert p4["test_set"]["total_functions"] == 40
    assert p4["test_set"]["intentional_drift_functions"] == 30
    assert p4["detection"]["precision"] >= 0.70
    assert p4["detection"]["recall"] >= 0.70
    assert p4["pipeline"]["ran"] is True
    assert p4["pipeline"]["qa_passed"] is True
    assert p4["pipeline"]["pr_success_rate"] >= 0.85
    assert p4["performance"]["total_latency_sec"] <= PROPOSAL_SECTION4_TARGETS["max_latency_sec"]
    assert p4["overall_pass"] is True
    assert (tmp_path / "proposal_pipeline" / "patch.diff").exists()


def test_benchmark_cli_command(tmp_path, capsys):
    code = main([
        "benchmark",
        str(FIXTURE),
        "-o",
        str(tmp_path),
    ])
    assert code == 0
    captured = capsys.readouterr()
    assert "Proposal S4" in captured.out
    assert "sample_project" in captured.out
    assert "Synthetic regression" in captured.out
    assert (tmp_path / "benchmark_report.json").exists()
    data = json.loads((tmp_path / "benchmark_report.json").read_text(encoding="utf-8"))
    assert data["curated"]["overall_pass"] is True
    assert data["realistic_fixtures"]["sample_project"]["precision"] < 1.0
