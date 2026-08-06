"""Human-in-the-loop approval gate and GitHub integration."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import subprocess

from docs_code_drift_detector.subprocess_compat import run_text


@dataclass
class ApprovalGate:
    run_id: str
    status: str  # pending | approved | rejected
    requires_human: bool
    hotl_approved: bool
    pr_url: str | None = None
    merge_blocked: bool = True
    message: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "status": self.status,
            "requires_human": self.requires_human,
            "hotl_approved": self.hotl_approved,
            "pr_url": self.pr_url,
            "merge_blocked": self.merge_blocked,
            "message": self.message,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


def create_approval_gate(
    run_id: str,
    *,
    requires_human: bool,
    hotl_approved: bool,
    pr_url: str | None = None,
    status: str | None = None,
) -> ApprovalGate:
    if status == "rejected":
        return ApprovalGate(
            run_id=run_id,
            status="rejected",
            requires_human=requires_human,
            hotl_approved=False,
            pr_url=pr_url,
            merge_blocked=True,
            message="Human rejected this run. No merge or PR continuation.",
        )
    if status == "approved" or (not requires_human or hotl_approved):
        return ApprovalGate(
            run_id=run_id,
            status="approved",
            requires_human=requires_human,
            hotl_approved=hotl_approved,
            pr_url=pr_url,
            merge_blocked=False,
            message="Approval gate passed.",
        )
    return ApprovalGate(
        run_id=run_id,
        status="pending",
        requires_human=True,
        hotl_approved=False,
        pr_url=pr_url,
        merge_blocked=True,
        message="Human approval required before merge. Review drift_report.json and patch.diff.",
    )


def update_gate_status(gate: ApprovalGate, status: str) -> ApprovalGate:
    """Update gate status from human review (approve / reject / reset pending)."""
    if status not in ("approved", "rejected", "pending"):
        raise ValueError(f"Invalid gate status: {status}")
    if status == "approved":
        return create_approval_gate(
            gate.run_id,
            requires_human=gate.requires_human,
            hotl_approved=True,
            pr_url=gate.pr_url,
            status="approved",
        )
    if status == "rejected":
        return create_approval_gate(
            gate.run_id,
            requires_human=gate.requires_human,
            hotl_approved=False,
            pr_url=gate.pr_url,
            status="rejected",
        )
    return create_approval_gate(
        gate.run_id,
        requires_human=gate.requires_human,
        hotl_approved=False,
        pr_url=gate.pr_url,
    )


def write_approval_gate(path: Path, gate: ApprovalGate) -> Path:
    path.write_text(json.dumps(gate.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def load_approval_gate(path: Path) -> ApprovalGate | None:
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    return ApprovalGate(
        run_id=data["run_id"],
        status=data["status"],
        requires_human=data.get("requires_human", False),
        hotl_approved=data.get("hotl_approved", False),
        pr_url=data.get("pr_url"),
        merge_blocked=data.get("merge_blocked", True),
        message=data.get("message", ""),
    )


def is_pending(gate: ApprovalGate) -> bool:
    return gate.status == "pending"


def post_pr_review_comment(pr_url: str, body: str) -> tuple[bool, str]:
    """Post HOTL instruction comment on GitHub PR via gh CLI."""
    try:
        result = run_text(
            ["gh", "pr", "comment", pr_url, "--body", body],
            capture_output=True,
            timeout=60,
        )
        if result.returncode == 0:
            return True, "Comment posted."
        return False, result.stderr.strip() or "gh pr comment failed"
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, str(exc)


def build_hotl_comment(report_summary: dict[str, Any]) -> str:
    return (
        "## Docs-Code Drift Detector — Human Approval Required (HOTL)\n\n"
        f"- Drifts detected: **{report_summary.get('drift_count', 0)}**\n"
        f"- QA passed: **{report_summary.get('qa_passed', False)}**\n\n"
        "Please review `patch.diff` (documentation only). "
        "Code changes are suggestions only and are **not** auto-applied.\n\n"
        "Approve by merging this PR after verification, or close to reject."
    )
