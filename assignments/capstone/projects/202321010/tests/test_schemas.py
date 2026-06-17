"""Tests for L7 schema registry."""

from docs_code_drift_detector.schemas import (
    SCHEMA_NAMES,
    load_schema,
    registry,
    validate_required_fields,
)


def test_registry_has_four_schemas():
    reg = registry()
    assert set(reg.keys()) == set(SCHEMA_NAMES)
    assert len(reg) == 4


def test_task_packet_schema_required_fields():
    schema = load_schema("task_packet")
    assert "task_id" in schema["required"]
    assert "assigned_role" in schema["required"]


def test_validate_required_fields_detects_missing():
    errors = validate_required_fields({"task_id": "x"}, "task_packet")
    assert len(errors) > 0
