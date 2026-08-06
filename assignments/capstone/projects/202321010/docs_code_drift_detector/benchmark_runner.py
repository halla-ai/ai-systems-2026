"""Proposal §4 benchmark: 30-function labeled set + optional full pipeline eval."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from docs_code_drift_detector.config import AppConfig
from docs_code_drift_detector.doc_analyzer import analyze_docs
from docs_code_drift_detector.drift_detector import detect_drift
from docs_code_drift_detector.llm_drift_reviewer import review_drifts_with_llm
from docs_code_drift_detector.models import DriftItem, DriftType
from docs_code_drift_detector.orchestrator import _function_level_code_specs
from docs_code_drift_detector.provider import select_provider

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "tests" / "fixtures"
GROUND_TRUTH_PATH = FIXTURES_DIR / "benchmark_ground_truth.json"
REALISTIC_GT_PATH = FIXTURES_DIR / "realistic_fixtures_ground_truth.json"
BENCHMARK_PROJECT = FIXTURES_DIR / "benchmark_project"
SAMPLE_PROJECT = FIXTURES_DIR / "sample_project"

STRUCTURAL_TYPES = {
    DriftType.RETURN_TYPE_MISMATCH,
    DriftType.PARAMETER_COUNT_MISMATCH,
    DriftType.PARAMETER_NAME_MISMATCH,
    DriftType.PARAMETER_TYPE_MISMATCH,
    DriftType.PARAMETER_DEFAULT_MISMATCH,
    DriftType.RETURN_STRUCTURE_MISMATCH,
}

# proposal.md §4 — labeled 30-drift + 10-clean evaluation targets
PROPOSAL_SECTION4_TARGETS = {
    "intentional_drift_functions": 30,
    "clean_functions": 10,
    "total_functions": 40,
    "category_counts": {
        "type_mismatch": 10,
        "parameter_mismatch": 10,
        "return_structure_mismatch": 10,
    },
    "min_precision": 0.70,
    "min_recall": 0.70,
    "max_false_positive_rate": 0.15,
    "min_pr_success_rate": 0.85,
    "max_latency_sec": 120.0,
    "max_cost_usd": 0.50,
}


@dataclass(frozen=True)
class DriftKey:
    module: str
    function: str
    drift_type: str

    @classmethod
    def from_drift(cls, d: DriftItem) -> DriftKey:
        dt = d.drift_type.value if isinstance(d.drift_type, DriftType) else str(d.drift_type)
        return cls(module=d.module, function=d.function, drift_type=dt)

    @classmethod
    def from_expected(cls, row: dict[str, str]) -> DriftKey:
        return cls(module=row["module"], function=row["function"], drift_type=row["drift_type"])


def load_ground_truth(path: Path | None = None) -> dict[str, Any]:
    gt_path = path or GROUND_TRUTH_PATH
    return json.loads(gt_path.read_text(encoding="utf-8"))


def run_detection(
    project_root: Path,
    *,
    use_llm: bool = False,
) -> tuple[list[DriftItem], int]:
    """Run analyzers + drift detection (no fix/QA/PR)."""
    code_specs = _function_level_code_specs(project_root)
    doc_specs = analyze_docs(project_root, code_specs=code_specs)
    drifts = detect_drift(doc_specs, code_specs)

    cfg = AppConfig.from_env(use_llm=use_llm)
    if cfg.use_llm:
        _, llm = select_provider(
            use_llm=True,
            api_key=cfg.openai_api_key,
            model=cfg.llm_model,
            cost_budget_usd=cfg.cost_budget_usd,
        )
        drifts, _ = review_drifts_with_llm(drifts, llm=llm)

    structural = [d for d in drifts if d.drift_type in STRUCTURAL_TYPES]
    return structural, len(code_specs)


def score_detection(
    detected: list[DriftItem],
    ground_truth: dict[str, Any],
    *,
    functions_scanned: int,
) -> dict[str, Any]:
    """Compute precision, recall, FPR vs labeled benchmark."""
    expected_rows = ground_truth.get("expected_drifts", [])
    expected = {DriftKey.from_expected(r) for r in expected_rows}
    detected_keys = {DriftKey.from_drift(d) for d in detected}

    tp_keys = expected & detected_keys
    fp_keys = detected_keys - expected
    fn_keys = expected - detected_keys

    tp = len(tp_keys)
    fp = len(fp_keys)
    fn = len(fn_keys)

    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0

    clean_functions = set(ground_truth.get("clean_functions", []))
    fp_functions = {k.function for k in fp_keys}
    clean_hits = fp_functions & clean_functions
    false_positive_rate = len(clean_hits) / functions_scanned if functions_scanned else 0.0

    by_category: dict[str, dict[str, Any]] = {}
    for row in expected_rows:
        cat = row.get("category", "unknown")
        key = DriftKey.from_expected(row)
        bucket = by_category.setdefault(cat, {"expected": 0, "tp": 0, "fn": 0})
        bucket["expected"] += 1
        if key in tp_keys:
            bucket["tp"] += 1
        elif key in fn_keys:
            bucket["fn"] += 1
        if bucket["expected"]:
            bucket["recall"] = round(bucket["tp"] / bucket["expected"], 3)

    targets = ground_truth.get("targets", {})
    proposal_targets = {**PROPOSAL_SECTION4_TARGETS, **targets}
    targets_met = {
        "precision": precision >= proposal_targets.get("min_precision", 0.70),
        "recall": recall >= proposal_targets.get("min_recall", 0.70),
        "false_positive_rate": false_positive_rate <= proposal_targets.get("max_false_positive_rate", 0.15),
    }
    overall_pass = all(targets_met.values())

    known_fp = {
        DriftKey(module=r["module"], function=r["function"], drift_type=r["drift_type"])
        for r in ground_truth.get("known_false_positives", [])
    }
    unexpected_fp = fp_keys - known_fp

    return {
        "tier": ground_truth.get("tier", "labeled"),
        "caveat": ground_truth.get("caveat"),
        "functions_scanned": functions_scanned,
        "expected_drifts": len(expected),
        "detected_drifts": len(detected_keys),
        "true_positives": tp,
        "false_positives": fp,
        "false_negatives": fn,
        "precision": round(precision, 3),
        "recall": round(recall, 3),
        "false_positive_rate": round(false_positive_rate, 3),
        "clean_functions_flagged": sorted(clean_hits),
        "missed": sorted(f"{k.module}.{k.function}:{k.drift_type}" for k in fn_keys),
        "unexpected": sorted(f"{k.module}.{k.function}:{k.drift_type}" for k in unexpected_fp),
        "known_false_positives_hit": sorted(
            f"{k.module}.{k.function}:{k.drift_type}" for k in (fp_keys & known_fp)
        ),
        "by_category": by_category,
        "targets": proposal_targets,
        "targets_met": targets_met,
        "overall_pass": overall_pass,
    }


def summarize_llm_usage(llm_meta: dict[str, Any] | None) -> dict[str, Any]:
    """Aggregate nested LLM call metadata from orchestrator worker steps."""
    if not llm_meta:
        return {
            "llm_enabled": False,
            "llm_used": False,
            "fallback_used": False,
            "estimated_cost_usd": 0.0,
            "provider": "",
        }

    total_cost = 0.0
    llm_called = False
    fallback = False

    def _walk(obj: Any) -> None:
        nonlocal total_cost, llm_called, fallback
        if not isinstance(obj, dict):
            return
        if obj.get("llm_used"):
            llm_called = True
        if obj.get("fallback_used"):
            fallback = True
        for key in ("estimated_cost_usd", "cost_usd", "total_cost_usd"):
            if key in obj and obj[key] is not None:
                total_cost += float(obj[key])
        for value in obj.values():
            if isinstance(value, dict):
                _walk(value)

    _walk(llm_meta)
    if "estimated_cost_usd" in llm_meta and llm_meta["estimated_cost_usd"] is not None:
        total_cost = max(total_cost, float(llm_meta["estimated_cost_usd"]))

    return {
        "llm_enabled": bool(llm_meta.get("enabled")),
        "llm_used": llm_called,
        "fallback_used": fallback,
        "estimated_cost_usd": round(total_cost, 6),
        "provider": str(llm_meta.get("provider", "")),
    }


def _llm_cost_usd(llm_meta: dict[str, Any]) -> float:
    return float(summarize_llm_usage(llm_meta)["estimated_cost_usd"])


def build_proposal_section4_report(
    *,
    ground_truth: dict[str, Any],
    detection_metrics: dict[str, Any],
    pipeline_result: Any = None,
    detection_latency_sec: float = 0.0,
    pipeline_latency_sec: float = 0.0,
    total_latency_sec: float = 0.0,
    full_pipeline: bool = False,
) -> dict[str, Any]:
    """Assemble proposal §4 evaluation block (detection + optional pipeline)."""
    targets = {**PROPOSAL_SECTION4_TARGETS, **ground_truth.get("targets", {})}
    detection_targets_met = dict(detection_metrics.get("targets_met", {}))

    pipeline_block: dict[str, Any] = {
        "ran": full_pipeline,
        "qa_passed": None,
        "pr_dry_run": None,
        "pr_success_rate": None,
        "run_id": None,
        "fix_invocations": None,
        "latency_sec": round(pipeline_latency_sec, 3) if full_pipeline else None,
        "llm_cost_usd": None,
    }
    pipeline_targets_met: dict[str, bool] = {}

    if full_pipeline and pipeline_result is not None:
        qa_passed = bool(pipeline_result.qa_passed)
        pr_success_rate = 1.0 if qa_passed else 0.0
        llm_summary = summarize_llm_usage(pipeline_result.llm_meta)
        llm_cost = float(llm_summary["estimated_cost_usd"])
        pipeline_block.update({
            "qa_passed": qa_passed,
            "pr_dry_run": pipeline_result.pr_url is None and not pipeline_result.review_verdict.get("abort_reason"),
            "pr_success_rate": pr_success_rate,
            "run_id": pipeline_result.run_id,
            "fix_invocations": pipeline_result.fix_invocations,
            "llm": llm_summary,
            "llm_cost_usd": round(llm_cost, 4),
            "review_verdict": pipeline_result.review_verdict.get("verdict"),
            "abort_reason": pipeline_result.review_verdict.get("abort_reason"),
        })
        pipeline_targets_met = {
            "pr_success_rate": pr_success_rate >= targets["min_pr_success_rate"],
            "latency_sec": total_latency_sec <= targets["max_latency_sec"],
            "llm_cost_usd": llm_cost <= targets["max_cost_usd"],
        }

    all_targets_met = {**detection_targets_met, **pipeline_targets_met}
    overall_pass = all(all_targets_met.values()) if full_pipeline else all(detection_targets_met.values())

    return {
        "section": "proposal_4",
        "description": ground_truth.get("description", "Proposal §4 large-scale validation"),
        "test_set": {
            "intentional_drift_functions": len(ground_truth.get("expected_drifts", [])),
            "clean_functions": len(ground_truth.get("clean_functions", [])),
            "total_functions": detection_metrics.get("functions_scanned", 0),
            "category_counts": {
                cat: detection_metrics.get("by_category", {}).get(cat, {}).get("expected", 0)
                for cat in targets["category_counts"]
            },
        },
        "detection": {
            **{k: detection_metrics[k] for k in (
                "precision", "recall", "false_positive_rate",
                "true_positives", "false_positives", "false_negatives",
                "expected_drifts", "detected_drifts", "by_category",
            ) if k in detection_metrics},
            "latency_sec": round(detection_latency_sec, 3),
        },
        "pipeline": pipeline_block,
        "performance": {
            "detection_latency_sec": round(detection_latency_sec, 3),
            "pipeline_latency_sec": round(pipeline_latency_sec, 3) if full_pipeline else None,
            "total_latency_sec": round(total_latency_sec, 3),
        },
        "targets": targets,
        "targets_met": {
            "detection": detection_targets_met,
            "pipeline": pipeline_targets_met,
            **all_targets_met,
        },
        "overall_pass": overall_pass,
    }


def run_proposal_section4_eval(
    project_root: Path | None = None,
    output_dir: Path | None = None,
    *,
    ground_truth_path: Path | None = None,
    use_llm: bool = False,
    detect_semantic: bool = False,
    full_pipeline: bool = True,
) -> dict[str, Any]:
    """Run proposal §4 eval: 30-drift detection (+ optional closed-loop pipeline)."""
    return run_benchmark(
        project_root,
        output_dir,
        ground_truth_path=ground_truth_path,
        use_llm=use_llm,
        detect_semantic=detect_semantic,
        full_pipeline=full_pipeline,
    )


def load_realistic_fixtures(path: Path | None = None) -> dict[str, Any]:
    gt_path = path or REALISTIC_GT_PATH
    return json.loads(gt_path.read_text(encoding="utf-8"))


def run_realistic_eval(
    *,
    use_llm: bool = False,
    fixtures_path: Path | None = None,
) -> dict[str, Any]:
    """Score hand-labeled fixtures (not tuned to the detector)."""
    catalog = load_realistic_fixtures(fixtures_path)
    rows: dict[str, Any] = {}

    repo_root = FIXTURES_DIR.parent.parent
    for name, spec in catalog.get("fixtures", {}).items():
        root = repo_root / spec["path"]
        if not root.exists():
            root = FIXTURES_DIR / name
        detected, n = run_detection(root, use_llm=use_llm)
        gt = {
            "expected_drifts": spec.get("expected_drifts", []),
            "clean_functions": spec.get("clean_functions", []),
            "known_false_positives": spec.get("known_false_positives", []),
            "targets": catalog.get("targets", {"min_precision": 0.70, "min_recall": 0.70, "max_false_positive_rate": 0.15}),
            "tier": "realistic",
            "caveat": spec.get("note"),
        }
        rows[name] = score_detection(detected, gt, functions_scanned=n)

    return rows


def run_benchmark(
    project_root: Path | None = None,
    output_dir: Path | None = None,
    *,
    ground_truth_path: Path | None = None,
    use_llm: bool = False,
    detect_semantic: bool = False,
    full_pipeline: bool = False,
) -> dict[str, Any]:
    """Run benchmark and write benchmark_report.json."""
    root = project_root or BENCHMARK_PROJECT
    out = output_dir or (Path(__file__).resolve().parent.parent / "benchmark_out")
    out.mkdir(parents=True, exist_ok=True)

    gt = load_ground_truth(ground_truth_path)
    pipeline_result = None
    t_total = time.monotonic()

    t_detect = time.monotonic()
    if full_pipeline:
        from docs_code_drift_detector.orchestrator import run_pipeline

        pipeline_out = out / "proposal_pipeline"
        pipeline_out.mkdir(parents=True, exist_ok=True)
        t_pipe = time.monotonic()
        pipeline_result = run_pipeline(
            root,
            pipeline_out,
            dry_run_pr=True,
            use_llm=use_llm,
            detect_semantic=detect_semantic or use_llm,
            hotl_approved=True,
        )
        pipeline_latency_sec = time.monotonic() - t_pipe
        detected = [
            d for d in pipeline_result.report.drifts if d.drift_type in STRUCTURAL_TYPES
        ]
        functions_scanned = pipeline_result.report.functions_scanned
        detection_latency_sec = 0.0
    else:
        detected, functions_scanned = run_detection(root, use_llm=use_llm)
        detection_latency_sec = time.monotonic() - t_detect
        pipeline_latency_sec = 0.0

    total_latency_sec = time.monotonic() - t_total
    metrics = score_detection(detected, gt, functions_scanned=functions_scanned)
    realistic = run_realistic_eval(use_llm=use_llm)

    proposal_section4 = build_proposal_section4_report(
        ground_truth=gt,
        detection_metrics=metrics,
        pipeline_result=pipeline_result,
        detection_latency_sec=detection_latency_sec,
        pipeline_latency_sec=pipeline_latency_sec if full_pipeline else 0.0,
        total_latency_sec=total_latency_sec,
        full_pipeline=full_pipeline,
    )
    metrics["overall_pass"] = proposal_section4["overall_pass"]
    if full_pipeline:
        metrics["pr_pipeline"] = {
            "qa_passed": pipeline_result.qa_passed if pipeline_result else False,
            "pr_success_rate": proposal_section4["pipeline"].get("pr_success_rate"),
            "run_id": pipeline_result.run_id if pipeline_result else None,
        }
        metrics["targets_met"] = proposal_section4["targets_met"].get("detection", metrics["targets_met"])
        metrics["targets_met"].update(proposal_section4["targets_met"].get("pipeline", {}))

    report = {
        "project": str(root),
        "mode": "full_pipeline" if full_pipeline else "detection_only",
        "use_llm": use_llm,
        "detect_semantic": detect_semantic or use_llm,
        "honesty_note": (
            "curated benchmark is synthetic and detector-aligned; "
            "prefer realistic_fixtures for credible precision."
        ),
        "proposal_section4": proposal_section4,
        "curated": metrics,
        "metrics": metrics,
        "realistic_fixtures": realistic,
        "detected": [d.to_dict() for d in detected],
    }
    report_path = out / "benchmark_report.json"
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    report["report_path"] = str(report_path)
    return report
