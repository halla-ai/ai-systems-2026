"""Week 6 — LLM-assisted doc parsing (type/parameter only, no semantic drift)."""

from __future__ import annotations

import json
import re
from typing import Any

from docs_code_drift_detector.models import FunctionSpec, ParameterSpec
from docs_code_drift_detector.provider.llm_provider import LLMProvider


def _normalize_return_type(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    if ":" in cleaned:
        cleaned = cleaned.split(":", 1)[0].strip()
    return cleaned


def parse_llm_doc_response(
    content: str,
    *,
    module: str = "llm_doc",
    source_file: str = "README.md",
) -> list[FunctionSpec]:
    """Convert LLM JSON response to FunctionSpec list."""
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        return []

    specs: list[FunctionSpec] = []
    for fn in data.get("functions", []):
        params = [
            ParameterSpec(
                name=p.get("name", ""),
                annotation=p.get("annotation"),
                default=str(p["default"]) if p.get("default") is not None else None,
            )
            for p in fn.get("parameters", [])
            if p.get("name")
        ]
        specs.append(
            FunctionSpec(
                name=fn.get("name", ""),
                module=module,
                parameters=params,
                return_annotation=_normalize_return_type(fn.get("return_annotation")),
                source_file=source_file,
                source="doc",
            )
        )
    return specs


def enhance_doc_specs_with_llm(
    readme_text: str,
    regex_specs: list[FunctionSpec],
    llm: LLMProvider | None,
) -> tuple[list[FunctionSpec], dict[str, Any]]:
    """
    Refine regex-parsed doc specs using LLM.
    Merges LLM output over regex where return types include descriptions.
    """
    meta: dict[str, Any] = {"llm_used": False, "enhanced_count": 0}

    if llm is None or not readme_text.strip():
        return regex_specs, meta

    prompt = (
        "Extract function API contracts from this README fragment.\n"
        "Only type and parameter structure — no semantic behavior.\n\n"
        f"{readme_text[:8000]}"
    )
    result = llm.complete(prompt)
    meta["llm_used"] = True
    meta["fallback_used"] = result.fallback_used
    meta["latency_sec"] = result.latency_sec
    meta["estimated_cost_usd"] = result.estimated_cost_usd

    llm_specs = parse_llm_doc_response(result.content)
    if not llm_specs:
        return regex_specs, meta

    by_name = {s.name: s for s in regex_specs}
    for spec in llm_specs:
        existing = by_name.get(spec.name)
        if existing is None:
            by_name[spec.name] = spec
            meta["enhanced_count"] += 1
            continue
        # Fix "dict: description" false positives from regex
        if existing.return_annotation and re.search(r":\s*\w", existing.return_annotation):
            existing.return_annotation = spec.return_annotation
            meta["enhanced_count"] += 1
        if not existing.parameters and spec.parameters:
            existing.parameters = spec.parameters
            meta["enhanced_count"] += 1

    return list(by_name.values()), meta
