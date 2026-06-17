"""Generate documentation patches and code fix suggestions."""

from __future__ import annotations

import difflib
import re
from pathlib import Path

from docs_code_drift_detector.models import (
    CodeFixSuggestion,
    DriftItem,
    DriftType,
    FixDirection,
    FunctionSpec,
    GovernanceDecision,
)
from docs_code_drift_detector.provider.llm_provider import LLMProvider


def _build_updated_signature(doc_spec: FunctionSpec, code_spec: FunctionSpec) -> str:
    params = ", ".join(
        _format_param(p) for p in code_spec.parameters
    )
    ret = code_spec.return_annotation or (
        code_spec.inferred_returns[0] if code_spec.inferred_returns else None
    )
    sig = f"{code_spec.name}({params})"
    if ret:
        sig += f" -> {ret}"
    return sig


def _format_param(param) -> str:
    if param.annotation:
        result = f"{param.name}: {param.annotation}"
    else:
        result = param.name
    if param.default is not None:
        result += f" = {param.default}"
    return result


def _replace_signature_in_readme(content: str, func_name: str, new_sig: str) -> str:
    patterns = [
        (
            re.compile(
                rf"`{re.escape(func_name)}\s*\([^`]*\)"
                rf"(?:\s*->\s*[^`]+)?`"
            ),
            f"`{new_sig}`",
        ),
        (
            re.compile(
                rf"(?<![a-zA-Z0-9_]){re.escape(func_name)}\s*\([^)\n]*\)"
                rf"(?:\s*->\s*[^\n`]+)?"
            ),
            new_sig,
        ),
    ]
    for pattern, replacement in patterns:
        if pattern.search(content):
            return pattern.sub(replacement, content, count=1)
    return content


def _replace_return_in_source_file(
    content: str,
    func_name: str,
    new_return: str,
) -> str:
    """Replace the Returns: value line inside func_name's docstring in source."""
    lines = content.splitlines(keepends=True)
    in_target = False
    in_docstring = False
    for i, line in enumerate(lines):
        if re.match(rf"^\s*def\s+{re.escape(func_name)}\s*\(", line):
            in_target = True
            in_docstring = False
            continue
        if in_target and '"""' in line:
            if not in_docstring:
                in_docstring = True
            else:
                in_target = False
                in_docstring = False
            continue
        if in_target and in_docstring and re.match(r"^\s*Returns?\s*:", line, re.I):
            if i + 1 < len(lines):
                indent_match = re.match(r"^(\s*)", lines[i + 1])
                indent = indent_match.group(1) if indent_match else "    "
                lines[i + 1] = f"{indent}{new_return}\n"
            break
    return "".join(lines)


def _replace_return_in_docstring(docstring: str, new_return: str) -> str:
    pattern = re.compile(
        r"(^\s*Returns?\s*:\s*)(.+)$",
        re.MULTILINE | re.IGNORECASE,
    )
    if pattern.search(docstring):
        return pattern.sub(rf"\g<1>{new_return}", docstring, count=1)
    return docstring + f"\n\nReturns:\n    {new_return}\n"


def _make_unified_diff(original: str, updated: str, rel_path: str) -> str:
    """Build a unified diff with correct line endings (Windows-safe)."""
    if original == updated:
        return ""
    rel = rel_path.replace("\\", "/")
    diff_lines = list(
        difflib.unified_diff(
            original.splitlines(),
            updated.splitlines(),
            fromfile=f"a/{rel}",
            tofile=f"b/{rel}",
            lineterm="",
        )
    )
    if not diff_lines:
        return ""
    return "\n".join(diff_lines) + "\n"


def _ensure_pending(
    pending: dict[str, tuple[str, str]],
    project_root: Path,
    rel_path: str,
) -> None:
    rel = rel_path.replace("\\", "/")
    if rel not in pending:
        text = (project_root / rel).read_text(encoding="utf-8")
        pending[rel] = (text, text)


def _update_pending(pending: dict[str, tuple[str, str]], rel_path: str, new_content: str) -> None:
    rel = rel_path.replace("\\", "/")
    orig, _ = pending[rel]
    pending[rel] = (orig, new_content)


def _apply_readme_updates_regex(
    readme_text: str,
    readme_updates: list[tuple[str, FunctionSpec, FunctionSpec]],
) -> str:
    """Fallback: regex signature replacement per function."""
    updated = readme_text
    for func_name, code, readme_doc in readme_updates:
        new_sig = _build_updated_signature(readme_doc, code)
        updated = _replace_signature_in_readme(updated, func_name, new_sig)
    return updated


def generate_doc_patch(
    project_root: Path,
    drifts: list[DriftItem],
    decisions: list[GovernanceDecision],
    code_specs: list[FunctionSpec],
    doc_specs: list[FunctionSpec],
    *,
    qa_retry: int = 0,
    qa_error: str = "",
    llm: LLMProvider | None = None,
    patch_meta: dict | None = None,
) -> str:
    """Generate unified diff for README/docstring documentation fixes."""
    decision_by_func: dict[tuple[str, str], GovernanceDecision] = {}
    direction_rank = {
        FixDirection.UPDATE_DOC: 0,
        FixDirection.SUGGEST_CODE: 1,
        FixDirection.HUMAN_REVIEW: 2,
    }
    for d in decisions:
        key = (d.module, d.function)
        prev = decision_by_func.get(key)
        if prev is None or direction_rank[d.direction] < direction_rank[prev.direction]:
            decision_by_func[key] = d
    code_by_key = {(s.module, s.name): s for s in code_specs}
    doc_by_key: dict[tuple[str, str], FunctionSpec] = {}
    for s in doc_specs:
        doc_by_key[(s.module, s.name)] = s
        doc_by_key[("readme", s.name)] = s

    pending: dict[str, tuple[str, str]] = {}
    readme_path = project_root / "README.md"
    readme_llm_updates: list = []
    readme_regex_updates: list[tuple[str, FunctionSpec, FunctionSpec]] = []

    drifts_by_func: dict[tuple[str, str], list[DriftItem]] = {}
    for drift in drifts:
        key = (drift.module, drift.function)
        drifts_by_func.setdefault(key, []).append(drift)

    for key, func_drifts in drifts_by_func.items():
        decision = decision_by_func.get(key)
        if decision and decision.direction != FixDirection.UPDATE_DOC:
            continue

        code = code_by_key.get(key)
        if code is None:
            continue

        func_name = key[1]
        readme_doc = doc_by_key.get(("readme", func_name))
        if readme_path.exists() and readme_doc:
            from docs_code_drift_detector.llm_readme_writer import build_readme_updates

            readme_llm_updates.append(
                build_readme_updates(
                    func_name=func_name,
                    code=code,
                    func_drifts=func_drifts,
                    readme_doc=readme_doc,
                )
            )
            readme_regex_updates.append((func_name, code, readme_doc))

        has_return_drift = any(
            d.drift_type in (
                DriftType.RETURN_TYPE_MISMATCH,
                DriftType.RETURN_STRUCTURE_MISMATCH,
            )
            for d in func_drifts
        )
        if code.docstring and code.has_docstring and has_return_drift:
            new_return = code.return_annotation or (
                code.inferred_returns[0] if code.inferred_returns else None
            )
            if new_return:
                rel = code.source_file.replace("\\", "/")
                _ensure_pending(pending, project_root, rel)
                _, current_file = pending[rel]
                updated_file = _replace_return_in_source_file(
                    current_file, func_name, new_return,
                )
                if updated_file != current_file:
                    _update_pending(pending, rel, updated_file)

    if readme_path.exists() and readme_regex_updates:
        _ensure_pending(pending, project_root, "README.md")
        orig_readme, _ = pending["README.md"]
        updated_readme: str | None = None

        if llm is not None and readme_llm_updates:
            from docs_code_drift_detector.llm_readme_writer import rewrite_readme_with_llm

            updated_readme, readme_meta = rewrite_readme_with_llm(
                orig_readme, readme_llm_updates, llm,
            )
            if patch_meta is not None:
                patch_meta["readme_llm"] = readme_meta

        if updated_readme is None:
            updated_readme = _apply_readme_updates_regex(
                orig_readme, readme_regex_updates,
            )

        if updated_readme != orig_readme:
            _update_pending(pending, "README.md", updated_readme)

    patches: list[str] = []
    for rel in sorted(pending):
        orig, updated = pending[rel]
        diff = _make_unified_diff(orig, updated, rel)
        if diff:
            patches.append(diff)

    result = "".join(patches)
    if qa_retry > 0:
        result = regenerate_patch_for_qa(result, qa_retry, qa_error)
    return result


def regenerate_patch_for_qa(
    patch_text: str,
    iteration: int,
    pytest_summary: str,
) -> str:
    """
    QA feedback: simplify patch lines on retry (strip 'type: description' suffixes).
    """
    if not patch_text.strip():
        return patch_text
    lines = []
    for line in patch_text.splitlines():
        if line.startswith("+") and "Returns:" not in line:
            # +    dict: Parsed data. -> +    dict
            m = re.match(r"^(\+\s*)([A-Za-z\[\],]+)\s*:\s*.+$", line)
            if m:
                lines.append(f"{m.group(1)}{m.group(2).split(':')[0].strip()}")
                continue
        lines.append(line)
    refined = "\n".join(lines)
    if refined == patch_text and iteration < 3:
        refined += f"\n# QA retry {iteration}: {pytest_summary[:80]}\n"
    return refined


def generate_code_suggestions(
    drifts: list[DriftItem],
    decisions: list[GovernanceDecision],
    code_specs: list[FunctionSpec],
) -> list[CodeFixSuggestion]:
    """Generate text-only code fix recommendations (no auto-apply)."""
    decision_by_func = {(d.module, d.function): d for d in decisions}
    code_by_key = {(s.module, s.name): s for s in code_specs}
    suggestions: list[CodeFixSuggestion] = []

    for drift in drifts:
        key = (drift.module, drift.function)
        decision = decision_by_func.get(key)
        if decision is None or decision.direction != FixDirection.SUGGEST_CODE:
            continue

        code = code_by_key.get(key)
        line_hint = code.line_number if code else None

        if drift.drift_type in (
            DriftType.RETURN_TYPE_MISMATCH,
            DriftType.RETURN_STRUCTURE_MISMATCH,
        ):
            message = (
                f"Alternative: update code to match documentation.\n"
                f"  - Expected return: {drift.doc_value}\n"
                f"  - Current return: {drift.code_value}\n"
                f"  - Consider changing return statements to produce {drift.doc_value}."
            )
        elif drift.drift_type == DriftType.PARAMETER_TYPE_MISMATCH:
            message = (
                f"Alternative: update parameter type annotation to match documentation.\n"
                f"  - Doc: {drift.doc_value}\n"
                f"  - Code: {drift.code_value}"
            )
        elif drift.drift_type == DriftType.PARAMETER_DEFAULT_MISMATCH:
            message = (
                f"Alternative: update default value to match documentation.\n"
                f"  - Doc default: {drift.doc_value}\n"
                f"  - Code default: {drift.code_value}"
            )
        else:
            message = (
                f"Alternative: update code to match documentation.\n"
                f"  - Doc: {drift.doc_value}\n"
                f"  - Code: {drift.code_value}"
            )

        suggestions.append(
            CodeFixSuggestion(
                function=drift.function,
                module=drift.module,
                message=message,
                line_hint=line_hint,
            )
        )

    return suggestions
