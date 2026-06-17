"""Apply documentation-only unified diffs for QA validation."""

from __future__ import annotations

import re
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path


@dataclass
class PatchApplyResult:
    success: bool
    temp_dir: Path | None
    files_modified: list[str]
    message: str


def _parse_unified_diff(patch_text: str) -> dict[str, list[tuple[str, str]]]:
    """Parse simple unified diff into per-file hunks."""
    files: dict[str, list[tuple[str, str]]] = {}
    current_file: str | None = None
    for line in patch_text.splitlines():
        if line.startswith("--- a/"):
            current_file = line[6:].strip().replace("\\", "/")
            files.setdefault(current_file, [])
        elif line.startswith("+++ b/") and current_file:
            pass
        elif current_file and (line.startswith("-") or line.startswith("+")):
            if line.startswith("---") or line.startswith("+++"):
                continue
            files[current_file].append((line[0], line[1:]))
    return files


def files_from_patch(patch_text: str) -> list[str]:
    """Return normalized relative paths referenced in a unified diff."""
    return list(_parse_unified_diff(patch_text).keys())


def _apply_hunks_to_lines(
    lines: list[str],
    hunks: list[tuple[str, str]],
) -> list[str]:
    """Apply +/- hunks to file lines (each line includes trailing newline)."""
    new_lines = list(lines)
    for op, text in hunks:
        line_text = text if text.endswith("\n") else text + "\n"
        if op == "-":
            for i, ln in enumerate(new_lines):
                if ln.rstrip("\n") == text.rstrip("\n"):
                    del new_lines[i]
                    break
        elif op == "+":
            if any(ln.rstrip("\n") == text.rstrip("\n") for ln in new_lines):
                continue
            inserted = False
            for i, ln in enumerate(new_lines):
                if re.match(r"\s*Returns?:", ln, re.I):
                    new_lines.insert(i + 1, line_text)
                    inserted = True
                    break
            if not inserted:
                new_lines.append(line_text)
    return new_lines


def apply_doc_patch_in_place(project_root: Path, patch_text: str) -> list[str]:
    """
    Apply doc-only patch hunks directly in project_root.
    Returns list of modified relative file paths.
    """
    if not patch_text.strip():
        return []

    modified: list[str] = []
    for rel_path, hunks in _parse_unified_diff(patch_text).items():
        target = project_root / rel_path
        if not target.exists():
            continue
        original_lines = target.read_text(encoding="utf-8").splitlines(keepends=True)
        new_lines = _apply_hunks_to_lines(original_lines, hunks)
        if new_lines != original_lines:
            target.write_text("".join(new_lines), encoding="utf-8")
            modified.append(rel_path)
    return modified


def apply_doc_patch_to_temp(
    project_root: Path,
    patch_text: str,
) -> PatchApplyResult:
    """
    Copy project to temp dir and apply doc-only patch hunks.
    Used by QA loop to validate patch does not break tests.
    """
    if not patch_text.strip():
        return PatchApplyResult(True, None, [], "Empty patch — nothing to apply.")

    file_changes = _parse_unified_diff(patch_text)
    if not file_changes:
        return PatchApplyResult(False, None, [], "Could not parse patch.diff")

    temp_dir = Path(tempfile.mkdtemp(prefix="drift_qa_"))
    try:
        shutil.copytree(
            project_root,
            temp_dir / "repo",
            ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache", ".git"),
            dirs_exist_ok=True,
        )
        repo = temp_dir / "repo"
        modified = apply_doc_patch_in_place(repo, patch_text)

        return PatchApplyResult(True, repo, modified, f"Applied patch to {len(modified)} file(s).")
    except OSError as exc:
        shutil.rmtree(temp_dir, ignore_errors=True)
        return PatchApplyResult(False, None, [], str(exc))
