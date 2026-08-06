"""Tests for fix generator."""

from pathlib import Path

from docs_code_drift_detector.code_analyzer import analyze_file
from docs_code_drift_detector.doc_analyzer import analyze_docs
from docs_code_drift_detector.drift_detector import detect_drift
from docs_code_drift_detector.fix_generator import generate_doc_patch
from docs_code_drift_detector.governance import apply_governance

FIXTURE = Path(__file__).parent / "fixtures" / "sample_project"


def test_generates_doc_patch():
    code_specs = analyze_file(FIXTURE / "api.py", FIXTURE)
    doc_specs = analyze_docs(FIXTURE, code_specs)
    drifts = detect_drift(doc_specs, code_specs)
    decisions = apply_governance(drifts, code_specs, FIXTURE)
    patch = generate_doc_patch(
        FIXTURE, drifts, decisions, code_specs, doc_specs
    )
    assert "README.md" in patch or "api.py" in patch or patch == ""


def test_patch_has_separate_plus_minus_lines():
    """Regression: diff lines must not merge '-...'+...' on one line (cp949/display bug)."""
    code_specs = analyze_file(FIXTURE / "api.py", FIXTURE)
    doc_specs = analyze_docs(FIXTURE, code_specs)
    drifts = detect_drift(doc_specs, code_specs)
    decisions = apply_governance(drifts, code_specs, FIXTURE)
    patch = generate_doc_patch(
        FIXTURE, drifts, decisions, code_specs, doc_specs,
    )
    assert patch
    for line in patch.splitlines():
        if line.startswith(("---", "+++", "@@")):
            continue
        if line.startswith("-") and "+" in line[1:]:
            raise AssertionError(f"Merged diff line: {line!r}")


def test_patch_includes_readme_and_docstring():
    code_specs = analyze_file(FIXTURE / "api.py", FIXTURE)
    doc_specs = analyze_docs(FIXTURE, code_specs)
    drifts = detect_drift(doc_specs, code_specs)
    decisions = apply_governance(drifts, code_specs, FIXTURE)
    patch = generate_doc_patch(
        FIXTURE, drifts, decisions, code_specs, doc_specs,
    )
    assert "--- a/README.md" in patch or "--- a/api.py" in patch
