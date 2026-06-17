"""LLM-assisted semantic mismatch detection (candidates only — no auto-fix)."""

from __future__ import annotations

import ast
import json
import re
from pathlib import Path
from typing import Any

from docs_code_drift_detector.models import DriftItem, DriftType, FunctionSpec
from docs_code_drift_detector.provider.llm_provider import LLMProvider

SEMANTIC_DETECT_PROMPT = """You detect SEMANTIC documentation-code mismatches only.
Compare what the documentation CLAIMS the function DOES vs what the code ACTUALLY DOES.

Output valid JSON only:
{
  "candidates": [
    {
      "mismatch": true,
      "doc_claim": "short description of documented behavior",
      "code_behavior": "short description of actual behavior",
      "confidence": 0.0,
      "reason": "why this is a semantic mismatch"
    }
  ]
}

Rules:
- mismatch=true ONLY for clear behavioral contradictions (e.g. doc says uppercase, code calls lower()).
- Do NOT report type/parameter/return-type differences (those are handled elsewhere).
- If uncertain, set mismatch=false or confidence below 0.7.
- No semantic speculation beyond the provided source snippet.
"""

MIN_SEMANTIC_CONFIDENCE = 0.7


def _extract_function_source(project_root: Path, spec: FunctionSpec) -> str:
    """Return function source text for LLM context."""
    path = project_root / spec.source_file
    if not path.exists():
        return ""
    try:
        content = path.read_text(encoding="utf-8")
        tree = ast.parse(content)
    except (OSError, SyntaxError):
        return ""

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == spec.name:
            lines = content.splitlines()
            start = node.lineno - 1
            end = (node.end_lineno or node.lineno) - 1
            return "\n".join(lines[start : end + 1])
    return ""


def _heuristic_semantic_candidate(
    spec: FunctionSpec,
    source: str,
) -> DriftItem | None:
    """Rule-based semantic checks when LLM is unavailable (demo / tests)."""
    doc = (spec.docstring or "").lower()
    src = source.lower()
    if not doc or not src:
        return None

    if re.search(r"upper|대문자", doc) and ".lower()" in src:
        return DriftItem(
            function=spec.name,
            module=spec.module,
            drift_type=DriftType.SEMANTIC_MISMATCH,
            doc_value="Document claims uppercase conversion",
            code_value="Code calls str.lower()",
            confidence=0.92,
            evidence={"doc": "uppercase", "code": ".lower()"},
            source_file=spec.source_file,
        )
    if re.search(r"sort|정렬", doc) and "sort(" not in src:
        return DriftItem(
            function=spec.name,
            module=spec.module,
            drift_type=DriftType.SEMANTIC_MISMATCH,
            doc_value="Document claims sorted result",
            code_value="No sort() in function body",
            confidence=0.85,
            evidence={"doc": "sorted", "code": "no sort"},
            source_file=spec.source_file,
        )
    return None


def _llm_semantic_candidate(
    spec: FunctionSpec,
    source: str,
    llm: LLMProvider,
) -> DriftItem | None:
    payload = {
        "function": spec.name,
        "module": spec.module,
        "docstring": spec.docstring,
        "source": source[:4000],
    }
    result = llm.complete(
        f"{SEMANTIC_DETECT_PROMPT}\n\nFunction:\n{json.dumps(payload, ensure_ascii=False)}",
        system="Semantic drift candidate detector. JSON only.",
    )
    if result.fallback_used:
        return None
    try:
        data = json.loads(result.content)
    except json.JSONDecodeError:
        return None

    for item in data.get("candidates", []):
        if not item.get("mismatch"):
            continue
        confidence = float(item.get("confidence", 0))
        if confidence < MIN_SEMANTIC_CONFIDENCE:
            continue
        return DriftItem(
            function=spec.name,
            module=spec.module,
            drift_type=DriftType.SEMANTIC_MISMATCH,
            doc_value=item.get("doc_claim"),
            code_value=item.get("code_behavior"),
            confidence=confidence,
            evidence={
                "doc": str(item.get("doc_claim", "")),
                "code": str(item.get("code_behavior", "")),
                "reason": str(item.get("reason", "")),
            },
            source_file=spec.source_file,
        )
    return None


def detect_semantic_drifts(
    project_root: Path,
    code_specs: list[FunctionSpec],
    llm: LLMProvider | None,
    *,
    use_heuristic_fallback: bool = True,
) -> tuple[list[DriftItem], dict[str, Any]]:
    """
    Detect semantic mismatch candidates. Never auto-fixes — for HITL review only.
    """
    meta: dict[str, Any] = {
        "enabled": True,
        "llm_used": False,
        "candidate_count": 0,
        "functions_checked": 0,
    }
    candidates: list[DriftItem] = []

    for spec in code_specs:
        if spec.name.startswith("_") or not spec.docstring:
            continue
        meta["functions_checked"] += 1
        source = _extract_function_source(project_root, spec)

        item: DriftItem | None = None
        if llm is not None:
            item = _llm_semantic_candidate(spec, source, llm)
            if item:
                meta["llm_used"] = True
        if item is None and use_heuristic_fallback:
            item = _heuristic_semantic_candidate(spec, source)

        if item:
            candidates.append(item)

    meta["candidate_count"] = len(candidates)
    return candidates, meta
