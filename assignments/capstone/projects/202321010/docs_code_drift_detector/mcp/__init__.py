"""MCP tool layer (L1)."""

from docs_code_drift_detector.mcp.protocol import (
    FORBIDDEN_TOOLS,
    TOOL_REGISTRY,
    get_allowed_tools,
    validate_tool_call,
)
from docs_code_drift_detector.mcp.tools import (
    filesystem_read,
    filesystem_write_doc_dry_run,
    github_pr_create_dry_run,
    pytest_run,
    scan_secrets_in_text,
)

__all__ = [
    "FORBIDDEN_TOOLS",
    "TOOL_REGISTRY",
    "get_allowed_tools",
    "validate_tool_call",
    "filesystem_read",
    "filesystem_write_doc_dry_run",
    "github_pr_create_dry_run",
    "pytest_run",
    "scan_secrets_in_text",
]
