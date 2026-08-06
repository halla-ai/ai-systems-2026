"""Tests for LLM README writer."""

import json
from unittest.mock import MagicMock

from docs_code_drift_detector.llm_readme_writer import (
    ReadmeUpdate,
    build_readme_updates,
    rewrite_readme_with_llm,
)
from docs_code_drift_detector.models import DriftItem, DriftType, FunctionSpec
from docs_code_drift_detector.provider.llm_provider import CompletionResult, LLMProvider


def test_rewrite_readme_with_llm_updates_content():
    readme = "# API\n\n`get_users(active: bool = True) -> list[dict]`\n"
    updates = [
        ReadmeUpdate(
            function="get_users",
            code_truth_signature="get_users(active: bool = False) -> dict",
            drifts=[{"drift_type": "return_structure_mismatch", "doc_value": "list[dict]", "code_value": "dict"}],
        )
    ]
    new_readme = "# API\n\n`get_users(active: bool = False) -> dict`\n"
    mock_llm = MagicMock()
    mock_llm.complete.return_value = CompletionResult(
        content=json.dumps({"readme": new_readme}),
        model="gpt-4o-mini",
        provider="test",
        latency_sec=0.1,
        estimated_cost_usd=0.001,
    )

    result, meta = rewrite_readme_with_llm(readme, updates, mock_llm)

    assert result == new_readme
    assert meta["readme_rewritten"] is True
    assert meta["llm_used"] is True
    mock_llm.complete.assert_called_once()


def test_rewrite_readme_fallback_on_no_key():
    readme = "# API\n"
    updates = [ReadmeUpdate("f", "f() -> int", [])]
    provider = LLMProvider(api_key=None)

    result, meta = rewrite_readme_with_llm(readme, updates, provider)

    assert result is None
    assert meta["fallback_used"] is True


def test_build_readme_updates_signature():
    code = FunctionSpec(
        name="get_users", module="utils",
        return_annotation="dict",
        source="code",
    )
    readme_doc = FunctionSpec(
        name="get_users", module="readme",
        return_annotation="list[dict]",
        source="doc",
    )
    drifts = [
        DriftItem(
            function="get_users", module="utils",
            drift_type=DriftType.RETURN_STRUCTURE_MISMATCH,
            doc_value="list[dict]", code_value="dict",
            confidence=0.9,
            evidence={"doc": "list[dict]", "code": "dict"},
        ),
    ]
    update = build_readme_updates(
        func_name="get_users", code=code, func_drifts=drifts, readme_doc=readme_doc,
    )
    assert "get_users" in update.code_truth_signature
    assert "dict" in update.code_truth_signature
