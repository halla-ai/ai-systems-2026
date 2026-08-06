"""MCP stdio server exposing drift detector tools (Week 3)."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from docs_code_drift_detector.mcp.protocol import TOOL_REGISTRY, get_allowed_tools
from docs_code_drift_detector.mcp.tools import (
    filesystem_read,
    github_pr_create_dry_run,
    pytest_run,
    scan_secrets_in_text,
)


def _handle_initialize(params: dict) -> dict:
    return {
        "protocolVersion": "2024-11-05",
        "capabilities": {"tools": {}},
        "serverInfo": {"name": "docs-code-drift-detector", "version": "0.2.0"},
    }


def _handle_tools_list() -> dict:
    tools = []
    for schema in get_allowed_tools():
        tools.append({
            "name": schema.name,
            "description": schema.description,
            "inputSchema": {
                "type": "object",
                "properties": {
                    k: {"type": v} for k, v in schema.input_fields.items()
                },
            },
        })
    tools.append({
        "name": "drift.scan",
        "description": "Run drift scan on a project directory.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_root": {"type": "string"},
                "output_dir": {"type": "string"},
            },
            "required": ["project_root"],
        },
    })
    return {"tools": tools}


def _handle_tools_call(name: str, arguments: dict) -> dict:
    if name == "filesystem.read":
        result = filesystem_read(Path(arguments["path"]))
    elif name == "pytest.run":
        result = pytest_run(Path(arguments["project_root"]), arguments.get("timeout_sec", 120))
    elif name == "github.pr_create":
        result = github_pr_create_dry_run(
            arguments.get("title", ""),
            arguments.get("body", ""),
            Path(arguments.get("patch_path", "patch.diff")),
        )
    elif name == "drift.scan":
        from docs_code_drift_detector.orchestrator import run_pipeline
        root = Path(arguments["project_root"])
        out = Path(arguments.get("output_dir", root / ".drift-output"))
        orch = run_pipeline(root, out, dry_run_pr=True)
        result_text = json.dumps({
            "drift_count": len(orch.report.drifts),
            "qa_passed": orch.qa_passed,
            "run_id": orch.run_id,
        })
        return {
            "content": [{"type": "text", "text": result_text}],
            "isError": len(orch.report.drifts) > 0,
        }
    else:
        return {
            "content": [{"type": "text", "text": f"Unknown tool: {name}"}],
            "isError": True,
        }

    return {
        "content": [{"type": "text", "text": json.dumps({
            "success": result.success,
            "output": result.output,
            "summary": result.summary,
        })}],
        "isError": not result.success,
    }


def _process_message(msg: dict) -> dict | None:
    method = msg.get("method")
    msg_id = msg.get("id")
    params = msg.get("params", {})

    if method == "initialize":
        result = _handle_initialize(params)
    elif method == "tools/list":
        result = _handle_tools_list()
    elif method == "tools/call":
        result = _handle_tools_call(params.get("name", ""), params.get("arguments", {}))
    elif method in ("notifications/initialized",):
        return None
    else:
        result = {"error": f"Unsupported method: {method}"}

    if msg_id is None:
        return None
    return {"jsonrpc": "2.0", "id": msg_id, "result": result}


def run_stdio_server() -> None:
    """Run MCP server on stdin/stdout."""
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
            response = _process_message(msg)
            if response:
                sys.stdout.write(json.dumps(response) + "\n")
                sys.stdout.flush()
        except json.JSONDecodeError:
            continue


if __name__ == "__main__":
    run_stdio_server()
