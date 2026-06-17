"""Tests for MCP stdio server message handling."""

from docs_code_drift_detector.mcp_server import _process_message


def test_mcp_initialize():
    resp = _process_message({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
    assert resp["id"] == 1
    assert resp["result"]["serverInfo"]["name"] == "docs-code-drift-detector"


def test_mcp_tools_list():
    resp = _process_message({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
    names = [t["name"] for t in resp["result"]["tools"]]
    assert "filesystem.read" in names
    assert "drift.scan" in names
