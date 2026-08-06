"""Tests for LLM drift reviewer heuristics."""

from docs_code_drift_detector.drift_detector import DriftType
from docs_code_drift_detector.llm_drift_reviewer import review_drifts_with_llm
from docs_code_drift_detector.models import DriftItem


def test_heuristic_filters_description_suffix_false_positive():
    drifts = [
        DriftItem(
            function="parse_json",
            module="api",
            drift_type=DriftType.RETURN_STRUCTURE_MISMATCH,
            doc_value="dict: Parsed data",
            code_value="dict",
            confidence=0.91,
            evidence={},
        )
    ]
    filtered, meta = review_drifts_with_llm(drifts, None)
    assert len(filtered) == 0
    assert meta["removed"] == 1


def test_llm_cannot_remove_confirmed_return_structure_drift():
    from unittest.mock import MagicMock

    from docs_code_drift_detector.provider.llm_provider import CompletionResult

    drifts = [
        DriftItem(
            function="get_users",
            module="utils",
            drift_type=DriftType.RETURN_STRUCTURE_MISMATCH,
            doc_value="list[dict]",
            code_value="dict",
            confidence=0.91,
            evidence={},
        )
    ]
    mock_llm = MagicMock()
    mock_llm.complete.return_value = CompletionResult(
        content='{"reviews": [{"function": "get_users", "drift_type": "return_structure_mismatch", "keep": false, "reason": "ok"}]}',
        model="test",
        provider="test",
        latency_sec=0.0,
        estimated_cost_usd=0.0,
    )
    filtered, meta = review_drifts_with_llm(drifts, mock_llm)
    assert len(filtered) == 1
    assert meta.get("llm_overrides")
