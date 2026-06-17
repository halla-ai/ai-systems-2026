"""Persist doc_spec.json and code_spec.json artifacts."""

from __future__ import annotations

import json
from pathlib import Path

from docs_code_drift_detector.models import FunctionSpec, ParameterSpec


def specs_to_dict(specs: list[FunctionSpec], *, kind: str, project_root: str) -> dict:
    return {
        "kind": kind,
        "project_root": project_root,
        "count": len(specs),
        "functions": [s.to_dict() for s in specs],
    }


def write_doc_spec(path: Path, specs: list[FunctionSpec], project_root: str) -> Path:
    data = specs_to_dict(specs, kind="doc_spec", project_root=project_root)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def write_code_spec(path: Path, specs: list[FunctionSpec], project_root: str) -> Path:
    data = specs_to_dict(specs, kind="code_spec", project_root=project_root)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def load_spec_file(path: Path) -> list[FunctionSpec]:
    data = json.loads(path.read_text(encoding="utf-8"))
    specs = []
    for fn in data.get("functions", []):
        params = [ParameterSpec(**p) for p in fn.get("parameters", [])]
        base = {k: v for k, v in fn.items() if k != "parameters"}
        specs.append(FunctionSpec(**base, parameters=params))
    return specs
