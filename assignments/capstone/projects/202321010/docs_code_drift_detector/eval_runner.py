"""Repeatability and fixture-based evaluation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from docs_code_drift_detector.config import AppConfig
from docs_code_drift_detector.orchestrator import run_pipeline


FIXTURE_EXPECTATIONS = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "eval_expectations.json"


def _load_expectations() -> dict[str, Any]:
    if not FIXTURE_EXPECTATIONS.exists():
        return {}
    return json.loads(FIXTURE_EXPECTATIONS.read_text(encoding="utf-8"))


def score_against_expectations(
    project_name: str,
    drift_report: dict[str, Any],
) -> dict[str, Any]:
    expectations = _load_expectations().get(project_name, {})
    if not expectations:
        return {"scored": False, "reason": "no expectations defined"}

    drifts = drift_report.get("drifts", [])
    found_functions = {d.get("function") for d in drifts}
    found_types = {d.get("drift_type") for d in drifts}

    required_functions = set(expectations.get("required_functions", []))
    required_types = set(expectations.get("required_types", []))
    min_count = expectations.get("min_drift_count", 0)

    fn_hits = required_functions & found_functions
    type_hits = required_types & found_types
    recall_functions = len(fn_hits) / len(required_functions) if required_functions else 1.0
    recall_types = len(type_hits) / len(required_types) if required_types else 1.0

    return {
        "scored": True,
        "drift_count": drift_report.get("drift_count", len(drifts)),
        "min_drift_count": min_count,
        "min_drift_met": drift_report.get("drift_count", len(drifts)) >= min_count,
        "required_functions": sorted(required_functions),
        "functions_found": sorted(fn_hits),
        "function_recall": round(recall_functions, 3),
        "required_types": sorted(required_types),
        "types_found": sorted(type_hits),
        "type_recall": round(recall_types, 3),
        "overall_pass": (
            drift_report.get("drift_count", len(drifts)) >= min_count
            and recall_functions >= expectations.get("min_function_recall", 1.0)
            and recall_types >= expectations.get("min_type_recall", 0.5)
        ),
    }


def run_repeatability_eval(
    project_root: Path,
    output_base: Path,
    *,
    runs: int = 3,
    dry_run_pr: bool = True,
    use_llm: bool = False,
    detect_semantic: bool = False,
) -> dict[str, Any]:
    output_base.mkdir(parents=True, exist_ok=True)
    run_rows: list[dict[str, Any]] = []

    config = AppConfig.from_env(
        use_llm=use_llm,
        detect_semantic=detect_semantic,
        dry_run_pr=dry_run_pr,
    )
    for i in range(1, runs + 1):
        out = output_base / f"run_{i}"
        result = run_pipeline(
            project_root,
            out,
            dry_run_pr=dry_run_pr,
            use_llm=use_llm,
            config=config,
        )
        report = result.report.to_dict()
        row = {
            "run_index": i,
            "run_id": result.run_id,
            "drift_count": len(result.report.drifts),
            "functions_scanned": result.report.functions_scanned,
            "qa_passed": result.qa_passed,
            "hotl_cycles": result.hotl_cycles,
            "review_verdict": result.review_verdict.get("verdict"),
            "llm_cost_usd": result.llm_meta.get("estimated_cost_usd", 0.0),
            "output_dir": str(out),
        }
        run_rows.append(row)

    drift_counts = [r["drift_count"] for r in run_rows]
    qa_flags = [r["qa_passed"] for r in run_rows]
    project_name = project_root.name
    eval_score = score_against_expectations(project_name, report)

    summary = {
        "project": str(project_root),
        "runs": runs,
        "repeatable": len(set(drift_counts)) == 1 and all(qa_flags),
        "drift_count_stable": len(set(drift_counts)) == 1,
        "drift_counts": drift_counts,
        "qa_all_passed": all(qa_flags),
        "run_rows": run_rows,
        "fixture_eval": eval_score,
    }
    summary_path = output_base / "eval_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    return summary
