"""Governance rules for deciding fix direction."""

from __future__ import annotations

import re
from pathlib import Path

from docs_code_drift_detector.models import (
    DriftItem,
    DriftType,
    FixDirection,
    FunctionSpec,
    GovernanceDecision,
)


def _function_has_tests(project_root: Path, func_name: str, module: str) -> bool:
    """Heuristic: check if test files reference the function name."""
    test_dirs = [project_root / "tests", project_root / "test"]
    patterns = [
        re.compile(rf"\b{re.escape(func_name)}\s*\("),
        re.compile(rf"test_{re.escape(func_name)}\b"),
    ]
    for test_dir in test_dirs:
        if not test_dir.exists():
            continue
        for test_file in test_dir.rglob("*.py"):
            try:
                content = test_file.read_text(encoding="utf-8")
            except OSError:
                continue
            if any(p.search(content) for p in patterns):
                return True
    return False


def _has_typing_annotations(spec: FunctionSpec) -> bool:
    if spec.return_annotation:
        return True
    return any(p.annotation for p in spec.parameters)


def _has_docstring_contract(spec: FunctionSpec) -> bool:
    if not spec.docstring:
        return False
    has_args = bool(
        re.search(r"(Args|Arguments|Parameters)\s*:", spec.docstring, re.IGNORECASE)
    )
    has_returns = bool(
        re.search(r"Returns?\s*:", spec.docstring, re.IGNORECASE)
    )
    return has_args or has_returns


def decide_fix_direction(
    drift: DriftItem,
    code_spec: FunctionSpec | None,
    project_root: Path,
) -> GovernanceDecision:
    """
    Apply governance rules:
    0. Semantic mismatch -> always human review (no auto patch)
    1. Tests exist -> code is source of truth (suggest doc update)
    2. Typing annotations exist -> code priority
    3. Explicit docstring contract -> consider doc priority
    4. Uncertain -> human review
    """
    if drift.drift_type == DriftType.SEMANTIC_MISMATCH:
        return GovernanceDecision(
            function=drift.function,
            module=drift.module,
            direction=FixDirection.HUMAN_REVIEW,
            reason="Semantic mismatch candidate (LLM); HITL review required. No auto patch.",
            has_tests=False,
            has_typing=False,
            has_docstring_contract=False,
        )

    has_tests = False
    has_typing = False
    has_doc_contract = False

    if code_spec:
        has_tests = _function_has_tests(project_root, code_spec.name, code_spec.module)
        has_typing = _has_typing_annotations(code_spec)
        has_doc_contract = _has_docstring_contract(code_spec)

    if has_tests:
        return GovernanceDecision(
            function=drift.function,
            module=drift.module,
            direction=FixDirection.UPDATE_DOC,
            reason="Tests exist; code is the source of truth.",
            has_tests=True,
            has_typing=has_typing,
            has_docstring_contract=has_doc_contract,
        )

    if has_typing:
        return GovernanceDecision(
            function=drift.function,
            module=drift.module,
            direction=FixDirection.UPDATE_DOC,
            reason="Typing annotations present; code takes priority.",
            has_tests=False,
            has_typing=True,
            has_docstring_contract=has_doc_contract,
        )

    if has_doc_contract:
        return GovernanceDecision(
            function=drift.function,
            module=drift.module,
            direction=FixDirection.SUGGEST_CODE,
            reason="Explicit docstring contract found; consider updating code.",
            has_tests=False,
            has_typing=False,
            has_docstring_contract=True,
        )

    return GovernanceDecision(
        function=drift.function,
        module=drift.module,
        direction=FixDirection.HUMAN_REVIEW,
        reason="Insufficient signals; human approval required.",
        has_tests=False,
        has_typing=False,
        has_docstring_contract=False,
    )


def apply_governance(
    drifts: list[DriftItem],
    code_specs: list[FunctionSpec],
    project_root: Path,
) -> list[GovernanceDecision]:
    """Generate governance decisions for all detected drifts."""
    code_by_key = {(s.module, s.name): s for s in code_specs}
    decisions: list[GovernanceDecision] = []
    seen: set[tuple[str, str]] = set()

    for drift in drifts:
        if drift.drift_type == DriftType.SEMANTIC_MISMATCH:
            code = code_by_key.get((drift.module, drift.function))
            decisions.append(decide_fix_direction(drift, code, project_root))
            continue
        key = (drift.module, drift.function)
        if key in seen:
            continue
        seen.add(key)
        code = code_by_key.get(key)
        decisions.append(decide_fix_direction(drift, code, project_root))

    return decisions
