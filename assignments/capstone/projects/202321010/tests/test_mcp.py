"""Tests for L1 MCP tool protocol."""

from pathlib import Path

from docs_code_drift_detector.mcp.protocol import (
    FORBIDDEN_TOOLS,
    validate_tool_call,
)
from docs_code_drift_detector.mcp.tools import (
    filesystem_read,
    github_pr_create_dry_run,
    pytest_run,
)


def test_forbidden_tools_include_code_modify():
    assert "code.modify" in FORBIDDEN_TOOLS
    assert "github.pr_create" not in FORBIDDEN_TOOLS


def test_validate_tool_call_allowed():
    ok, msg = validate_tool_call("filesystem.read")
    assert ok is True


def test_validate_tool_call_forbidden():
    ok, msg = validate_tool_call("code.modify")
    assert ok is False
    assert "forbidden" in msg.lower()


def test_github_pr_requires_hotl():
    ok, msg = validate_tool_call("github.pr_create", create_pr=True, hotl_approved=False)
    assert ok is False
    assert "hotl" in msg.lower()


def test_filesystem_read(tmp_path):
    f = tmp_path / "test.txt"
    f.write_text("hello", encoding="utf-8")
    result = filesystem_read(f)
    assert result.success is True
    assert result.output["content"] == "hello"


def test_github_pr_create_is_dry_run_only():
    result = github_pr_create_dry_run("title", "body", Path("patch.diff"))
    assert result.output["dry_run"] is True
    assert result.output["pr_url"] is None


def test_pytest_run_no_tests_dir(tmp_path):
    result = pytest_run(tmp_path)
    assert result.success is True
    assert "skipped" in result.summary.lower() or result.output["passed"] is True
