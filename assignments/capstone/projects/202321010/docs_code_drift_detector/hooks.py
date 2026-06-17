"""L6 Hook Lifecycle — approval, secret scan, loop stop, escalation."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from docs_code_drift_detector.mcp.tools import scan_secrets_in_text
from docs_code_drift_detector.models import FixDirection, GovernanceDecision


@dataclass
class HookResult:
    hook_name: str
    passed: bool
    action: str  # continue | stop | escalate | require_approval
    message: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "hook_name": self.hook_name,
            "passed": self.passed,
            "action": self.action,
            "message": self.message,
        }


def approval_hook(
    decisions: list[GovernanceDecision],
    *,
    hotl_approved: bool = False,
) -> HookResult:
    """Week 1 HOTL — block auto-PR path if human_review required without approval."""
    human_needed = [
        d for d in decisions if d.direction == FixDirection.HUMAN_REVIEW
    ]
    if human_needed and not hotl_approved:
        return HookResult(
            hook_name="approval",
            passed=False,
            action="require_approval",
            message=(
                f"HOTL required: {len(human_needed)} function(s) need human approval "
                "before PR merge."
            ),
        )
    return HookResult(
        hook_name="approval",
        passed=True,
        action="continue",
        message="Approval check passed (or no human_review decisions).",
    )


def secret_scan_hook(patch_text: str, report_text: str = "") -> HookResult:
    """Scan patch and report for potential secrets before PR."""
    combined = patch_text + "\n" + report_text
    findings = scan_secrets_in_text(combined)
    if findings:
        return HookResult(
            hook_name="secret_scan",
            passed=False,
            action="stop",
            message=f"Potential secrets detected: {findings[:3]}",
        )
    return HookResult(
        hook_name="secret_scan",
        passed=True,
        action="continue",
        message="No secrets detected in patch/report.",
    )


def loop_stop_hook(
    iteration: int,
    max_iterations: int,
    *,
    pytest_passed: bool,
    review_approved: bool,
) -> HookResult:
    """Week 4 QA Loop — stop when pytest passes + approved, or max iterations."""
    if pytest_passed and review_approved:
        return HookResult(
            hook_name="loop_stop",
            passed=True,
            action="stop",
            message=f"QA loop complete at iteration {iteration}: tests passed.",
        )
    if iteration >= max_iterations:
        return HookResult(
            hook_name="loop_stop",
            passed=False,
            action="stop",
            message=f"QA loop stopped at max iterations ({max_iterations}).",
        )
    return HookResult(
        hook_name="loop_stop",
        passed=True,
        action="continue",
        message=f"Continue QA loop (iteration {iteration}/{max_iterations}).",
    )


def escalation_hook(
    decisions: list[GovernanceDecision],
    drift_count: int,
    *,
    threshold: int = 3,
) -> HookResult:
    """Escalate to human when uncertain decisions exceed threshold."""
    uncertain = sum(
        1 for d in decisions if d.direction == FixDirection.HUMAN_REVIEW
    )
    if uncertain >= threshold or (drift_count > 10 and uncertain > 0):
        return HookResult(
            hook_name="escalation",
            passed=False,
            action="escalate",
            message=(
                f"Escalation triggered: {uncertain} human_review decision(s), "
                f"{drift_count} total drifts."
            ),
        )
    return HookResult(
        hook_name="escalation",
        passed=True,
        action="continue",
        message="No escalation needed.",
    )


def validate_doc_only_patch(patch_text: str) -> HookResult:
    """Ensure patch does not modify non-documentation code logic."""
    if not patch_text.strip():
        return HookResult(
            hook_name="doc_only_patch",
            passed=True,
            action="continue",
            message="Empty patch — nothing to validate.",
        )
    # Reject patches that change function bodies beyond docstring Returns lines
    risky = re.findall(r"^\+(?!\s*(#|\"\"\"|\'\'\'|Returns:)).*def ", patch_text, re.M)
    if risky:
        return HookResult(
            hook_name="doc_only_patch",
            passed=False,
            action="stop",
            message="Patch may modify code logic — rejected.",
        )
    return HookResult(
        hook_name="doc_only_patch",
        passed=True,
        action="continue",
        message="Patch appears documentation-only.",
    )


def run_all_hooks(
    *,
    decisions: list[GovernanceDecision],
    patch_text: str,
    report_text: str,
    drift_count: int,
    hotl_approved: bool = False,
) -> list[HookResult]:
    return [
        secret_scan_hook(patch_text, report_text),
        validate_doc_only_patch(patch_text),
        approval_hook(decisions, hotl_approved=hotl_approved),
        escalation_hook(decisions, drift_count),
    ]


def blocking_hooks(hook_results: list[HookResult]) -> list[HookResult]:
    """Hooks with action=stop that must abort the pipeline."""
    return [h for h in hook_results if not h.passed and h.action == "stop"]
