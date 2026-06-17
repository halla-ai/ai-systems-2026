"""Tests for API doc parser."""

from pathlib import Path

from docs_code_drift_detector.api_doc_parser import discover_api_docs, parse_openapi

FIXTURE = Path(__file__).parent / "fixtures" / "sample_project"


def test_parse_openapi():
    specs = parse_openapi(FIXTURE / "openapi.yaml")
    by_name = {s.name: s for s in specs}
    assert "parse_json" in by_name
    assert "fetch_items" in by_name
    assert by_name["fetch_items"].return_annotation == "list[dict]"


def test_discover_api_docs():
    specs = discover_api_docs(FIXTURE)
    names = {s.name for s in specs}
    assert "parse_json" in names
