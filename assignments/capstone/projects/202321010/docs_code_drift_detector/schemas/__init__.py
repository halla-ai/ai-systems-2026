"""L7 Schema IPC Registry."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

SCHEMA_DIR = Path(__file__).parent

SCHEMA_NAMES = (
    "task_packet",
    "worker_report",
    "review_verdict",
    "run_report",
)


def load_schema(name: str) -> dict[str, Any]:
    path = SCHEMA_DIR / f"{name}.schema.json"
    return json.loads(path.read_text(encoding="utf-8"))


def validate_required_fields(data: dict[str, Any], schema_name: str) -> list[str]:
    """Lightweight validation against required fields in schema."""
    schema = load_schema(schema_name)
    required = schema.get("required", [])
    errors = [f"Missing required field: {f}" for f in required if f not in data]
    return errors


def registry() -> dict[str, dict[str, Any]]:
    return {name: load_schema(name) for name in SCHEMA_NAMES}
