"""Tests for spec JSON artifacts."""

from pathlib import Path

from docs_code_drift_detector.code_analyzer import analyze_file
from docs_code_drift_detector.doc_analyzer import analyze_docs
from docs_code_drift_detector.spec_io import write_code_spec, write_doc_spec

FIXTURE = Path(__file__).parent / "fixtures" / "sample_project"


def test_write_doc_and_code_spec(tmp_path):
    code = analyze_file(FIXTURE / "api.py", FIXTURE)
    doc = analyze_docs(FIXTURE, code)
    write_doc_spec(tmp_path / "doc_spec.json", doc, str(FIXTURE))
    write_code_spec(tmp_path / "code_spec.json", code, str(FIXTURE))
    assert (tmp_path / "doc_spec.json").exists()
    assert (tmp_path / "code_spec.json").exists()
    import json
    data = json.loads((tmp_path / "doc_spec.json").read_text(encoding="utf-8"))
    assert data["kind"] == "doc_spec"
    assert data["count"] >= 1
