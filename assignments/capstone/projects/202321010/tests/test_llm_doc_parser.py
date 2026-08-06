"""Tests for LLM doc parser."""

import json

from docs_code_drift_detector.llm_doc_parser import (
    enhance_doc_specs_with_llm,
    parse_llm_doc_response,
)
from docs_code_drift_detector.models import FunctionSpec
from docs_code_drift_detector.provider.llm_provider import LLMProvider


def test_parse_llm_doc_response():
    content = json.dumps({
        "functions": [{
            "name": "parse_json",
            "parameters": [{"name": "data", "annotation": "str"}],
            "return_annotation": "dict",
        }]
    })
    specs = parse_llm_doc_response(content)
    assert specs[0].name == "parse_json"
    assert specs[0].return_annotation == "dict"


def test_enhance_doc_specs_without_llm():
    regex_specs = [
        FunctionSpec(
            name="f", module="m",
            return_annotation="dict: parsed",
            source="doc",
        )
    ]
    specs, meta = enhance_doc_specs_with_llm("readme", regex_specs, None)
    assert meta["llm_used"] is False
    assert len(specs) == 1


def test_llm_provider_fallback_without_key():
    provider = LLMProvider(api_key=None)
    result = provider.complete("extract docs")
    assert result.fallback_used is True
    data = json.loads(result.content)
    assert "fallback_reason" in data
