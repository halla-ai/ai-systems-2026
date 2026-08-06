"""LLM-assisted README rewriting (documentation-only, code-aligned signatures)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from docs_code_drift_detector.fix_generator import _build_updated_signature
from docs_code_drift_detector.models import DriftItem, FunctionSpec
from docs_code_drift_detector.provider.llm_provider import LLMProvider

README_REWRITE_SYSTEM_PROMPT = """You update README API documentation to match Python code contracts.
Output valid JSON only:
{
  "readme": "<full updated README markdown>"
}

Rules:
- Align listed function signatures (parameters, defaults, return types) to CODE TRUTH.
- Preserve existing structure, headings, and descriptive prose (including non-English text).
- Change only API reference content for functions listed in updates.
- Documentation only — do not modify or invent code behavior semantics.
- Use exact type annotations from code_truth (e.g. dict, list[dict], bool = False).
"""


@dataclass
class ReadmeUpdate:
    function: str
    code_truth_signature: str
    drifts: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "function": self.function,
            "code_truth_signature": self.code_truth_signature,
            "drifts": self.drifts,
        }


def build_readme_updates(
    *,
    func_name: str,
    code: FunctionSpec,
    func_drifts: list[DriftItem],
    readme_doc: FunctionSpec,
) -> ReadmeUpdate:
    """Build a single README update payload for the LLM."""
    return ReadmeUpdate(
        function=func_name,
        code_truth_signature=_build_updated_signature(readme_doc, code),
        drifts=[
            {
                "drift_type": d.drift_type.value if hasattr(d.drift_type, "value") else str(d.drift_type),
                "doc_value": d.doc_value,
                "code_value": d.code_value,
            }
            for d in func_drifts
        ],
    )


def rewrite_readme_with_llm(
    readme_text: str,
    updates: list[ReadmeUpdate],
    llm: LLMProvider,
) -> tuple[str | None, dict[str, Any]]:
    """
    Rewrite README via LLM API. Returns (updated_readme, meta) or (None, meta) on fallback.
    """
    meta: dict[str, Any] = {
        "llm_used": False,
        "readme_rewritten": False,
        "update_count": len(updates),
    }
    if not readme_text.strip() or not updates:
        return None, meta

    payload = {
        "readme": readme_text,
        "updates": [u.to_dict() for u in updates],
    }
    user_prompt = (
        "Update the README so drifting API entries match code_truth_signature.\n\n"
        f"{json.dumps(payload, ensure_ascii=False, indent=2)}"
    )
    result = llm.complete(user_prompt, system=README_REWRITE_SYSTEM_PROMPT)
    meta.update({
        "llm_used": True,
        "fallback_used": result.fallback_used,
        "latency_sec": result.latency_sec,
        "estimated_cost_usd": result.estimated_cost_usd,
        "model": result.model,
    })

    if result.fallback_used:
        return None, meta

    try:
        data = json.loads(result.content)
    except json.JSONDecodeError:
        meta["error"] = "invalid_json"
        return None, meta

    new_readme = data.get("readme", "")
    if not isinstance(new_readme, str) or not new_readme.strip():
        meta["error"] = "empty_readme"
        return None, meta

    if new_readme == readme_text:
        meta["readme_rewritten"] = False
        return None, meta

    meta["readme_rewritten"] = True
    return new_readme, meta
