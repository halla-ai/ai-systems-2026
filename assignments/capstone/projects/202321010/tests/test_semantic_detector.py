"""Tests for semantic mismatch detection (HITL candidates)."""

from pathlib import Path

from docs_code_drift_detector.code_analyzer import analyze_file
from docs_code_drift_detector.governance import apply_governance
from docs_code_drift_detector.llm_semantic_detector import detect_semantic_drifts
from docs_code_drift_detector.models import DriftType, FixDirection

TESTPROJECT = Path(__file__).parent.parent / "testproject"


def test_heuristic_detects_to_upper_semantic():
    specs = analyze_file(TESTPROJECT / "testproject" / "utils.py", TESTPROJECT)
    drifts, meta = detect_semantic_drifts(TESTPROJECT, specs, llm=None)
    names = {d.function for d in drifts}
    assert "to_upper" in names
    assert drifts[0].drift_type == DriftType.SEMANTIC_MISMATCH
    assert meta["candidate_count"] >= 1


def test_semantic_governance_is_human_review():
    specs = analyze_file(TESTPROJECT / "testproject" / "utils.py", TESTPROJECT)
    drifts, _ = detect_semantic_drifts(TESTPROJECT, specs, llm=None)
    decisions = apply_governance(drifts, specs, TESTPROJECT)
    semantic_decisions = [
        d for d in decisions if d.direction == FixDirection.HUMAN_REVIEW
    ]
    assert len(semantic_decisions) >= 1
    assert "Semantic mismatch" in semantic_decisions[0].reason
