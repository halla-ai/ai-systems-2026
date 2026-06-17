"""Tests for drift detection."""

from pathlib import Path

from docs_code_drift_detector.code_analyzer import analyze_file
from docs_code_drift_detector.doc_analyzer import analyze_docs
from docs_code_drift_detector.drift_detector import detect_drift
from docs_code_drift_detector.models import DriftType

FIXTURE = Path(__file__).parent / "fixtures" / "sample_project"


def _run_detection():
    code_specs = analyze_file(FIXTURE / "api.py", FIXTURE)
    doc_specs = analyze_docs(FIXTURE, code_specs)
    return detect_drift(doc_specs, code_specs)


def test_detects_return_type_mismatch():
    drifts = _run_detection()
    types = {(d.function, d.drift_type) for d in drifts}
    assert ("parse_json", DriftType.RETURN_TYPE_MISMATCH) in types or (
        "parse_json",
        DriftType.RETURN_STRUCTURE_MISMATCH,
    ) in types


def test_detects_parameter_default_mismatch():
    drifts = _run_detection()
    defaults = [
        d for d in drifts if d.drift_type == DriftType.PARAMETER_DEFAULT_MISMATCH
    ]
    assert any(d.function == "greet" for d in defaults)


def test_detects_return_structure_mismatch():
    drifts = _run_detection()
    structure = [
        d
        for d in drifts
        if d.drift_type == DriftType.RETURN_STRUCTURE_MISMATCH
        and d.function == "fetch_items"
    ]
    assert len(structure) >= 1
    assert structure[0].doc_value is not None
    assert structure[0].code_value is not None
