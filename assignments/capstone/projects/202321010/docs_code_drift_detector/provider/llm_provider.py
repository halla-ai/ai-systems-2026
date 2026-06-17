"""L2 LLM Provider — OpenAI completion with cost/latency budget and fallback."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any

from docs_code_drift_detector.provider.static_provider import (
    LLM_DOC_PARSER_STUB,
    REGEX_ONLY_PROFILE,
    STATIC_AST_PROFILE,
    ProviderProfile,
)


@dataclass
class CompletionResult:
    content: str
    model: str
    provider: str
    latency_sec: float
    estimated_cost_usd: float
    fallback_used: bool = False
    raw: dict[str, Any] = field(default_factory=dict)


DOC_PARSE_SYSTEM_PROMPT = """You are a documentation structure extractor.
Extract ONLY explicit type and parameter contracts from README/docstring text.
Output valid JSON only:
{
  "functions": [
    {
      "name": "func_name",
      "parameters": [{"name": "x", "annotation": "str", "default": null}],
      "return_annotation": "dict"
    }
  ]
}
Rules:
- Do NOT infer semantic behavior (sorting, validation, side effects).
- Do NOT report semantic drift.
- If type is ambiguous, use null for that field.
- Strip descriptions from return types (e.g. "dict: parsed data" -> "dict").
"""


class LLMProvider:
    """OpenAI-compatible chat completion with static fallback."""

    def __init__(
        self,
        api_key: str | None,
        model: str = "gpt-4o-mini",
        cost_budget_usd: float = 0.50,
        latency_budget_sec: float = 30.0,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.cost_budget_usd = cost_budget_usd
        self.latency_budget_sec = latency_budget_sec
        self._spent_usd = 0.0

    @property
    def profile(self) -> ProviderProfile:
        return LLM_DOC_PARSER_STUB

    def complete(self, user_prompt: str, *, system: str = DOC_PARSE_SYSTEM_PROMPT) -> CompletionResult:
        if not self.api_key:
            return self._heuristic_fallback(user_prompt, reason="no_api_key")
        if self._spent_usd >= self.cost_budget_usd:
            return self._heuristic_fallback(user_prompt, reason="cost_budget_exceeded")

        start = time.monotonic()
        try:
            payload = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": 0,
                "response_format": {"type": "json_object"},
            }
            req = urllib.request.Request(
                "https://api.openai.com/v1/chat/completions",
                data=json.dumps(payload).encode("utf-8"),
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=self.latency_budget_sec) as resp:
                body = json.loads(resp.read().decode("utf-8"))
            latency = time.monotonic() - start
            content = body["choices"][0]["message"]["content"]
            usage = body.get("usage", {})
            cost = _estimate_cost(self.model, usage)
            self._spent_usd += cost
            return CompletionResult(
                content=content,
                model=self.model,
                provider="openai",
                latency_sec=latency,
                estimated_cost_usd=cost,
                raw=body,
            )
        except (urllib.error.URLError, TimeoutError, KeyError, json.JSONDecodeError) as exc:
            return self._heuristic_fallback(user_prompt, reason=str(exc))

    def _heuristic_fallback(self, user_prompt: str, reason: str) -> CompletionResult:
        return CompletionResult(
            content=json.dumps({"functions": [], "fallback_reason": reason}),
            model=REGEX_ONLY_PROFILE.name,
            provider="static-fallback",
            latency_sec=0.0,
            estimated_cost_usd=0.0,
            fallback_used=True,
        )


def _estimate_cost(model: str, usage: dict[str, Any]) -> float:
    """Rough cost estimate for gpt-4o-mini."""
    prompt_tokens = usage.get("prompt_tokens", 0)
    completion_tokens = usage.get("completion_tokens", 0)
    if "mini" in model:
        return (prompt_tokens * 0.15 + completion_tokens * 0.60) / 1_000_000
    return (prompt_tokens * 2.5 + completion_tokens * 10.0) / 1_000_000


def select_provider(
    *,
    use_llm: bool,
    api_key: str | None,
    model: str = "gpt-4o-mini",
    cost_budget_usd: float = 0.50,
) -> tuple[ProviderProfile, LLMProvider | None]:
    if use_llm and api_key:
        provider = LLMProvider(api_key, model=model, cost_budget_usd=cost_budget_usd)
        return provider.profile, provider
    if use_llm:
        return LLM_DOC_PARSER_STUB, None
    return STATIC_AST_PROFILE, None
