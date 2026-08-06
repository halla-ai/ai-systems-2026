"""Tests for L6 hooks."""

from docs_code_drift_detector.governance import apply_governance
from docs_code_drift_detector.hooks import (
    blocking_hooks,
    approval_hook,
    escalation_hook,
    run_all_hooks,
    secret_scan_hook,
    validate_doc_only_patch,
)
from docs_code_drift_detector.models import FixDirection, GovernanceDecision


def test_secret_scan_detects_api_key():
    result = secret_scan_hook("api_key=sk-abc123")
    assert result.passed is False
    assert result.action == "stop"


def test_secret_scan_ignores_type_annotations():
    result = secret_scan_hook("`struct_06(token: str) -> list`")
    assert result.passed is True


def test_approval_hook_requires_hotl():
    decisions = [
        GovernanceDecision(
            function="f", module="m", direction=FixDirection.HUMAN_REVIEW,
            reason="uncertain", has_tests=False, has_typing=False,
            has_docstring_contract=False,
        )
    ]
    result = approval_hook(decisions, hotl_approved=False)
    assert result.passed is False
    assert result.action == "require_approval"


def test_validate_doc_only_patch_accepts_docstring_change():
    patch = "--- a/api.py\n+++ b/api.py\n@@\n-    dict\n+    list\n"
    result = validate_doc_only_patch(patch)
    assert result.passed is True


def test_run_all_hooks(tmp_path):
    decisions = []
    result = run_all_hooks(
        decisions=decisions,
        patch_text="",
        report_text="{}",
        drift_count=0,
    )
    assert len(result) == 4


def test_blocking_hooks_returns_stop_failures():
    failed = secret_scan_hook("token=ghp_secretvalue1234567890")
    blockers = blocking_hooks([failed])
    assert len(blockers) == 1
    assert blockers[0].action == "stop"
