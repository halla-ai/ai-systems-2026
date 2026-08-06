"""L1 MCP Tool Protocol — allowed/forbidden tools, I/O schema, tool events."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ToolPermission(str, Enum):
    ALLOWED = "allowed"
    FORBIDDEN = "forbidden"
    DRY_RUN_ONLY = "dry_run_only"


@dataclass
class ToolIOSchema:
    name: str
    input_fields: dict[str, str]
    output_fields: dict[str, str]
    permission: ToolPermission
    description: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "permission": self.permission.value,
            "description": self.description,
            "input_schema": self.input_fields,
            "output_schema": self.output_fields,
        }


TOOL_REGISTRY: dict[str, ToolIOSchema] = {
    "filesystem.read": ToolIOSchema(
        name="filesystem.read",
        input_fields={"path": "string", "encoding": "string"},
        output_fields={"content": "string", "exists": "boolean"},
        permission=ToolPermission.ALLOWED,
        description="Read README, source files, and reports.",
    ),
    "filesystem.write_doc": ToolIOSchema(
        name="filesystem.write_doc",
        input_fields={"path": "string", "content": "string"},
        output_fields={"written": "boolean"},
        permission=ToolPermission.DRY_RUN_ONLY,
        description="Write documentation patches only (via patch.diff, not direct code edit).",
    ),
    "pytest.run": ToolIOSchema(
        name="pytest.run",
        input_fields={"project_root": "string", "timeout_sec": "integer"},
        output_fields={"passed": "boolean", "exit_code": "integer", "summary": "string"},
        permission=ToolPermission.ALLOWED,
        description="Run pytest for QA validation.",
    ),
    "github.pr_create": ToolIOSchema(
        name="github.pr_create",
        input_fields={"title": "string", "body": "string", "patch_path": "string"},
        output_fields={"pr_url": "string", "dry_run": "boolean"},
        permission=ToolPermission.ALLOWED,
        description="Create PR via gh CLI — gated by HOTL approval hook.",
    ),
    "llm.complete": ToolIOSchema(
        name="llm.complete",
        input_fields={"prompt": "string", "model": "string"},
        output_fields={"content": "string", "estimated_cost_usd": "number"},
        permission=ToolPermission.ALLOWED,
        description="LLM doc structure extraction (type/parameter only).",
    ),
    "code.modify": ToolIOSchema(
        name="code.modify",
        input_fields={"path": "string", "patch": "string"},
        output_fields={"applied": "boolean"},
        permission=ToolPermission.FORBIDDEN,
        description="FORBIDDEN — code auto-modification not allowed.",
    ),
}


FORBIDDEN_TOOLS = {
    name for name, schema in TOOL_REGISTRY.items()
    if schema.permission == ToolPermission.FORBIDDEN
}


def get_allowed_tools() -> list[ToolIOSchema]:
    return [
        s for s in TOOL_REGISTRY.values()
        if s.permission in (ToolPermission.ALLOWED, ToolPermission.DRY_RUN_ONLY)
    ]


def validate_tool_call(
    tool_name: str,
    *,
    hotl_approved: bool = False,
    create_pr: bool = False,
) -> tuple[bool, str]:
    schema = TOOL_REGISTRY.get(tool_name)
    if schema is None:
        return False, f"Unknown tool: {tool_name}"
    if schema.permission == ToolPermission.FORBIDDEN:
        return False, f"Tool '{tool_name}' is forbidden by MCP protocol."
    if tool_name == "github.pr_create" and create_pr and not hotl_approved:
        return False, "github.pr_create requires HOTL approval (--hotl-approved)."
    return True, "ok"
