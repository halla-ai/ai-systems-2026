"""MCP tool implementations (Week 3 — filesystem, pytest, GitHub dry-run)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import subprocess

from docs_code_drift_detector.mcp.protocol import (
    ToolPermission,
    TOOL_REGISTRY,
    validate_tool_call,
)
from docs_code_drift_detector.subprocess_compat import run_text


@dataclass
class ToolResult:
    tool: str
    success: bool
    output: dict
    summary: str


def filesystem_read(path: Path, encoding: str = "utf-8") -> ToolResult:
    ok, msg = validate_tool_call("filesystem.read")
    if not ok:
        return ToolResult("filesystem.read", False, {}, msg)
    if not path.exists():
        return ToolResult(
            "filesystem.read", True,
            {"content": "", "exists": False},
            f"File not found: {path}",
        )
    content = path.read_text(encoding=encoding)
    return ToolResult(
        "filesystem.read", True,
        {"content": content, "exists": True, "path": str(path)},
        f"Read {len(content)} bytes from {path.name}",
    )


def filesystem_write_doc_dry_run(path: Path, content: str) -> ToolResult:
    """Dry-run only — reports what would be written, does not write."""
    schema = TOOL_REGISTRY["filesystem.write_doc"]
    if schema.permission != ToolPermission.DRY_RUN_ONLY:
        return ToolResult("filesystem.write_doc", False, {}, "Not in dry-run mode.")
    return ToolResult(
        "filesystem.write_doc", True,
        {"written": False, "would_write_path": str(path), "bytes": len(content)},
        f"Dry-run: would write {len(content)} bytes to {path.name}",
    )


def pytest_run(project_root: Path, timeout_sec: int = 120) -> ToolResult:
    ok, msg = validate_tool_call("pytest.run")
    if not ok:
        return ToolResult("pytest.run", False, {}, msg)

    tests_dir = project_root / "tests"
    if not tests_dir.exists():
        return ToolResult(
            "pytest.run", True,
            {"passed": True, "exit_code": 0, "summary": "No tests/ directory — skipped."},
            "pytest skipped (no tests)",
        )

    try:
        result = run_text(
            ["python", "-m", "pytest", "tests", "-q", "--tb=no"],
            cwd=str(project_root),
            capture_output=True,
            timeout=timeout_sec,
        )
        passed = result.returncode == 0
        summary = (result.stdout or result.stderr or "").strip()[:500]
        return ToolResult(
            "pytest.run", True,
            {"passed": passed, "exit_code": result.returncode, "summary": summary},
            f"pytest exit_code={result.returncode}",
        )
    except subprocess.TimeoutExpired:
        return ToolResult(
            "pytest.run", False,
            {"passed": False, "exit_code": -1, "summary": "timeout"},
            f"pytest timed out after {timeout_sec}s",
        )
    except FileNotFoundError:
        return ToolResult(
            "pytest.run", False,
            {"passed": False, "exit_code": -1, "summary": "pytest not found"},
            "pytest executable not found",
        )


def github_pr_create_dry_run(title: str, body: str, patch_path: Path) -> ToolResult:
    return ToolResult(
        "github.pr_create", True,
        {
            "pr_url": None,
            "dry_run": True,
            "title": title,
            "body_preview": body[:200],
            "patch_path": str(patch_path),
        },
        "Dry-run PR preview generated (gh not executed).",
    )


def github_pr_create(
    title: str,
    body: str,
    patch_path: Path,
    *,
    hotl_approved: bool,
    base_branch: str = "main",
    draft: bool = False,
) -> ToolResult:
    ok, msg = validate_tool_call(
        "github.pr_create", hotl_approved=hotl_approved, create_pr=True,
    )
    if not ok:
        return ToolResult("github.pr_create", False, {}, msg)

    from docs_code_drift_detector.pr_agent import GhPRAgent, PRRequest

    agent = GhPRAgent()
    request = PRRequest(
        title=title, body=body, patch_path=patch_path,
        base_branch=base_branch, draft=draft or not hotl_approved,
    )
    result = agent.create_pr(request)
    return ToolResult(
        "github.pr_create", result.success,
        {"pr_url": result.pr_url, "dry_run": False, "message": result.message},
        result.message,
    )


SECRET_PATTERNS = [
    re.compile(r"(?i)(api[_-]?key|secret|password|token)\s*[:=]\s*\S+"),
    re.compile(r"-----BEGIN [A-Z ]+-----"),
]

_TYPE_ANNOTATION_VALUES = frozenset({
    "str", "int", "bool", "float", "dict", "list", "none", "optional", "any",
    "bytes", "set", "tuple", "object",
})


def _secret_match_is_type_annotation(match_text: str) -> bool:
    """Skip doc/README signatures like `token: str` (not real secrets)."""
    sep = ":" if ":" in match_text else "="
    value = match_text.split(sep, 1)[-1].strip().rstrip(")`]}>,.")
    head = value.split("[", 1)[0].lower()
    return head in _TYPE_ANNOTATION_VALUES


def scan_secrets_in_text(text: str) -> list[str]:
    findings = []
    for pattern in SECRET_PATTERNS:
        for match in pattern.finditer(text):
            snippet = match.group(0)[:80]
            if _secret_match_is_type_annotation(snippet):
                continue
            findings.append(snippet)
    return findings
