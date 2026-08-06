"""Parse OpenAPI and Sphinx API documentation."""

from __future__ import annotations

import json
import re
from pathlib import Path

from docs_code_drift_detector.doc_analyzer import _parse_params, _normalize_type
from docs_code_drift_detector.models import FunctionSpec, ParameterSpec

try:
    import yaml
except ImportError:
    yaml = None  # type: ignore


def _openapi_type(schema: dict) -> str | None:
    if not schema:
        return None
    if "$ref" in schema:
        ref = schema["$ref"].split("/")[-1]
        return ref
    t = schema.get("type")
    if t == "array":
        items = schema.get("items", {})
        inner = _openapi_type(items) or "any"
        return f"list[{inner}]"
    if t == "object":
        return "dict"
    if t:
        return str(t)
    return None


def parse_openapi(path: Path) -> list[FunctionSpec]:
    """Extract operation schemas from OpenAPI 3.x JSON/YAML."""
    text = path.read_text(encoding="utf-8")
    if path.suffix in (".yaml", ".yml"):
        if yaml is None:
            return []
        data = yaml.safe_load(text)
    else:
        data = json.loads(text)

    specs: list[FunctionSpec] = []
    module = f"openapi:{path.stem}"
    paths = data.get("paths", {})
    for route, methods in paths.items():
        if not isinstance(methods, dict):
            continue
        for method, op in methods.items():
            if method.startswith("x-") or not isinstance(op, dict):
                continue
            op_id = op.get("operationId") or f"{method}_{route.strip('/').replace('/', '_')}"
            params: list[ParameterSpec] = []
            for p in op.get("parameters", []):
                schema = p.get("schema", {})
                params.append(
                    ParameterSpec(
                        name=p.get("name", ""),
                        annotation=_openapi_type(schema) or p.get("type"),
                    )
                )
            for p in op.get("requestBody", {}).get("content", {}).values():
                schema = p.get("schema", {})
                if schema:
                    params.append(ParameterSpec(name="body", annotation=_openapi_type(schema)))

            responses = op.get("responses", {})
            ret = None
            for code in ("200", "201", "default"):
                if code in responses:
                    content = responses[code].get("content", {})
                    for media in content.values():
                        ret = _openapi_type(media.get("schema", {}))
                        break
                if ret:
                    break

            specs.append(
                FunctionSpec(
                    name=op_id,
                    module=module,
                    parameters=params,
                    return_annotation=ret,
                    source_file=str(path.name),
                    source="doc",
                )
            )
    return specs


_SPHINX_AUTO_RE = re.compile(
    r"\.\.\s+(?:autofunction|py:function|automethod)::\s*([\w.]+)",
    re.MULTILINE,
)
_SPHINX_SIG_RE = re.compile(
    r"``([a-zA-Z_][\w]*)\s*\(([^)]*)\)(?:\s*->\s*([^`]+))?``"
)


def parse_sphinx_docs(path: Path) -> list[FunctionSpec]:
    """Extract function references from Sphinx RST files."""
    content = path.read_text(encoding="utf-8")
    specs: dict[str, FunctionSpec] = {}
    module = f"sphinx:{path.stem}"

    for match in _SPHINX_AUTO_RE.finditer(content):
        full_name = match.group(1)
        name = full_name.split(".")[-1]
        specs[name] = FunctionSpec(
            name=name, module=module, source_file=str(path.name), source="doc",
        )

    for match in _SPHINX_SIG_RE.finditer(content):
        name = match.group(1)
        params = _parse_params(match.group(2) or "")
        ret = _normalize_type(match.group(3))
        specs[name] = FunctionSpec(
            name=name,
            module=module,
            parameters=params,
            return_annotation=ret,
            source_file=str(path.name),
            source="doc",
        )

    return list(specs.values())


def discover_api_docs(project_root: Path) -> list[FunctionSpec]:
    """Find and parse OpenAPI + Sphinx API docs under project."""
    specs: dict[str, FunctionSpec] = {}
    patterns = [
        "openapi.json", "openapi.yaml", "openapi.yml",
        "swagger.json", "api.yaml", "api.yml",
    ]
    for name in patterns:
        p = project_root / name
        if p.exists():
            for s in parse_openapi(p):
                specs[s.name] = s

    for docs_dir in ("docs", "doc", "documentation"):
        root = project_root / docs_dir
        if root.exists():
            for rst in root.rglob("*.rst"):
                for s in parse_sphinx_docs(rst):
                    specs[s.name] = s
            for spec_file in root.rglob("openapi.*"):
                if spec_file.suffix in (".json", ".yaml", ".yml"):
                    for s in parse_openapi(spec_file):
                        specs[s.name] = s

    return list(specs.values())
