"""Pipeline-level drift recall for sample_project fixture."""

from pathlib import Path

from docs_code_drift_detector.drift_detector import DriftType
from docs_code_drift_detector.eval_runner import score_against_expectations
from docs_code_drift_detector.llm_drift_reviewer import review_drifts_with_llm
from docs_code_drift_detector.orchestrator import run_pipeline

FIXTURE = Path(__file__).parent / "fixtures" / "sample_project"


def test_greet_default_survives_heuristic_review():
    from docs_code_drift_detector.code_analyzer import analyze_file
    from docs_code_drift_detector.doc_analyzer import analyze_docs
    from docs_code_drift_detector.drift_detector import detect_drift

    code_specs = analyze_file(FIXTURE / "api.py", FIXTURE)
    doc_specs = analyze_docs(FIXTURE, code_specs)
    raw = detect_drift(doc_specs, code_specs)
    filtered, _meta = review_drifts_with_llm(raw, None)
    defaults = [
        d for d in filtered
        if d.function == "greet" and d.drift_type == DriftType.PARAMETER_DEFAULT_MISMATCH
    ]
    assert len(defaults) == 1
    assert defaults[0].doc_value == "False"
    assert defaults[0].code_value == "True"


def test_fixture_eval_passes_after_scan(tmp_path):
    result = run_pipeline(FIXTURE, tmp_path, dry_run_pr=True)
    report = result.report.to_dict()
    score = score_against_expectations("sample_project", report)
    assert score["function_recall"] == 1.0
    assert score["overall_pass"] is True
