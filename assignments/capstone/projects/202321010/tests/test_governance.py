"""Tests for governance rules."""

from pathlib import Path

from docs_code_drift_detector.code_analyzer import analyze_file
from docs_code_drift_detector.doc_analyzer import analyze_docs
from docs_code_drift_detector.drift_detector import detect_drift
from docs_code_drift_detector.governance import apply_governance, decide_fix_direction
from docs_code_drift_detector.models import FixDirection

FIXTURE = Path(__file__).parent / "fixtures" / "sample_project"


def test_governance_prefers_code_when_tests_exist():
    code_specs = analyze_file(FIXTURE / "api.py", FIXTURE)
    doc_specs = analyze_docs(FIXTURE, code_specs)
    drifts = detect_drift(doc_specs, code_specs)
    parse_drift = next(d for d in drifts if d.function == "parse_json")
    code = next(s for s in code_specs if s.name == "parse_json")

    decision = decide_fix_direction(parse_drift, code, FIXTURE)
    assert decision.has_tests is True
    assert decision.direction == FixDirection.UPDATE_DOC


def test_apply_governance_returns_decisions():
    code_specs = analyze_file(FIXTURE / "api.py", FIXTURE)
    doc_specs = analyze_docs(FIXTURE, code_specs)
    drifts = detect_drift(doc_specs, code_specs)
    decisions = apply_governance(drifts, code_specs, FIXTURE)
    assert len(decisions) >= 1
