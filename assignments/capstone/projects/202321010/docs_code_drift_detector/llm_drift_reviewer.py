"""LLM-assisted drift review — structural/type drifts only (no semantic)."""

from __future__ import annotations

import json
import re
from typing import Any

from docs_code_drift_detector.models import DriftItem, DriftType
from docs_code_drift_detector.provider.llm_provider import LLMProvider

DRIFT_REVIEW_PROMPT = """Review these documentation-code drifts.
ONLY confirm or reject structural/type/parameter mismatches.
Do NOT flag semantic behavior differences.

Return JSON:
{
  "reviews": [
    {"function": "name", "drift_type": "...", "keep": true, "reason": "..."}
  ]
}

Reject (keep=false) if doc_value includes a description suffix like "dict: parsed data"
when code_value is the base type "dict" — that is a parsing artifact, not real drift.
"""


def _normalize_type_token(value: str | None) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if ":" in text:
        text = text.split(":", 1)[0].strip()
    return text.lower()


def _is_confirmed_structural_drift(drift: DriftItem) -> bool:
    """True when doc/code types clearly differ (LLM must not discard)."""
    if drift.drift_type not in (
        DriftType.RETURN_TYPE_MISMATCH,
        DriftType.RETURN_STRUCTURE_MISMATCH,
        DriftType.PARAMETER_TYPE_MISMATCH,
        DriftType.PARAMETER_DEFAULT_MISMATCH,
    ):
        return False
    doc_v = _normalize_type_token(drift.doc_value)
    code_v = _normalize_type_token(drift.code_value)
    if not code_v:
        return False
    if drift.drift_type == DriftType.PARAMETER_DEFAULT_MISMATCH:
        return drift.doc_value is not None and str(drift.doc_value) != str(drift.code_value)
    return bool(doc_v) and doc_v != code_v


def _heuristic_review(drift: DriftItem) -> dict[str, Any]:
    """Rule-based false positive filter without LLM."""
    keep = True
    reason = "structural drift confirmed"

    if drift.drift_type == DriftType.RETURN_STRUCTURE_MISMATCH:
        doc_v = (drift.doc_value or "").strip()
        code_v = (drift.code_value or "").strip()
        if ":" in doc_v:
            base = doc_v.split(":", 1)[0].strip().lower()
            if base == code_v.lower():
                keep = False
                reason = "doc_value includes description suffix; base types match"

    if drift.drift_type == DriftType.PARAMETER_DEFAULT_MISMATCH:
        if drift.doc_value is None and drift.code_value:
            keep = False
            reason = "doc default missing in parse; not confirmed mismatch"
        elif drift.doc_value is not None and str(drift.doc_value) != str(drift.code_value):
            keep = True
            reason = "parameter default mismatch confirmed"

    return {
        "function": drift.function,
        "drift_type": drift.drift_type.value,
        "keep": keep,
        "reason": reason,
    }


def review_drifts_with_llm(
    drifts: list[DriftItem],
    llm: LLMProvider | None,
) -> tuple[list[DriftItem], dict[str, Any]]:
    """
    Filter false-positive drifts using LLM or heuristics.
    Does NOT add semantic mismatch detection.
    """
    meta: dict[str, Any] = {"llm_used": False, "removed": 0}

    if not drifts:
        return drifts, meta

    if llm is None:
        reviews = [_heuristic_review(d) for d in drifts]
    else:
        payload = json.dumps([
            {
                "function": d.function,
                "drift_type": d.drift_type.value,
                "doc_value": d.doc_value,
                "code_value": d.code_value,
            }
            for d in drifts
        ], ensure_ascii=False)
        result = llm.complete(
            f"{DRIFT_REVIEW_PROMPT}\n\nDrifts:\n{payload}",
            system="You filter false positive type/parameter drifts only. Output JSON.",
        )
        meta["llm_used"] = True
        meta["fallback_used"] = result.fallback_used
        meta["estimated_cost_usd"] = result.estimated_cost_usd
        try:
            data = json.loads(result.content)
            reviews = data.get("reviews", [])
        except json.JSONDecodeError:
            reviews = [_heuristic_review(d) for d in drifts]

    review_by_key = {
        (r["function"], r["drift_type"]): r for r in reviews
    }
    filtered: list[DriftItem] = []
    for drift in drifts:
        review = review_by_key.get(
            (drift.function, drift.drift_type.value),
            _heuristic_review(drift),
        )
        keep = review.get("keep", True)
        if not keep and _is_confirmed_structural_drift(drift):
            keep = True
            meta.setdefault("llm_overrides", []).append({
                "function": drift.function,
                "drift_type": drift.drift_type.value,
                "reason": "confirmed structural drift preserved",
            })
        if keep:
            filtered.append(drift)
        else:
            meta["removed"] += 1

    return filtered, meta
