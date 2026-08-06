"""Tests for code_analyzer module."""

from pathlib import Path

from docs_code_drift_detector.code_analyzer import analyze_file, analyze_project

FIXTURE = Path(__file__).parent / "fixtures" / "sample_project"
API_FILE = FIXTURE / "api.py"


def test_analyze_file_extracts_function_names():
    specs = analyze_file(API_FILE, FIXTURE)
    names = {s.name for s in specs}
    assert "parse_json" in names
    assert "greet" in names
    assert "fetch_items" in names


def test_analyze_file_extracts_parameters():
    specs = analyze_file(API_FILE, FIXTURE)
    parse_json = next(s for s in specs if s.name == "parse_json")
    assert len(parse_json.parameters) == 1
    assert parse_json.parameters[0].name == "data"
    assert parse_json.parameters[0].annotation == "str"


def test_analyze_file_extracts_return_annotation():
    specs = analyze_file(API_FILE, FIXTURE)
    parse_json = next(s for s in specs if s.name == "parse_json")
    assert parse_json.return_annotation == "list"


def test_analyze_file_infers_return_types():
    specs = analyze_file(API_FILE, FIXTURE)
    parse_json = next(s for s in specs if s.name == "parse_json")
    assert "list" in parse_json.inferred_returns

    fetch_items = next(s for s in specs if s.name == "fetch_items")
    assert "dict" in fetch_items.inferred_returns


def test_analyze_file_extracts_default_values():
    specs = analyze_file(API_FILE, FIXTURE)
    greet = next(s for s in specs if s.name == "greet")
    loud = next(p for p in greet.parameters if p.name == "loud")
    assert loud.default == "True"


def test_analyze_project_finds_python_files():
    specs = analyze_project(FIXTURE, exclude_dirs={".git", "venv", "__pycache__"})
    names = {s.name for s in specs}
    assert "parse_json" in names
