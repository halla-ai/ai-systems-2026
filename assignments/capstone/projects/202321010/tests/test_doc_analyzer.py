"""Tests for doc_analyzer module."""

from pathlib import Path

from docs_code_drift_detector.code_analyzer import analyze_file
from docs_code_drift_detector.doc_analyzer import analyze_docs, parse_readme

FIXTURE = Path(__file__).parent / "fixtures" / "sample_project"


def test_parse_readme_extracts_signatures():
    specs = parse_readme(FIXTURE / "README.md")
    by_name = {s.name: s for s in specs}
    assert "parse_json" in by_name
    assert by_name["parse_json"].return_annotation == "dict"
    assert by_name["parse_json"].parameters[0].annotation == "str"


def test_parse_readme_extracts_parameter_defaults():
    specs = parse_readme(FIXTURE / "README.md")
    greet = next(s for s in specs if s.name == "greet")
    loud = next(p for p in greet.parameters if p.name == "loud")
    assert loud.default == "False"


def test_analyze_docs_includes_docstrings():
    code_specs = analyze_file(FIXTURE / "api.py", FIXTURE)
    doc_specs = analyze_docs(FIXTURE, code_specs)
    fetch = next(s for s in doc_specs if s.name == "fetch_items")
    assert fetch.return_annotation == "list[dict]"
