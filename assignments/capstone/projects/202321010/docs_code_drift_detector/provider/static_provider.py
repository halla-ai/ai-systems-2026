"""L2 Provider Completion — static analysis provider profile (no LLM in MVP)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ProviderProfile:
    name: str
    provider_type: str  # "static" | "llm"
    model: str | None = None
    cost_budget_usd: float = 0.0
    latency_budget_sec: float = 120.0
    fallback_chain: list[str] = field(default_factory=list)
    description: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "provider_type": self.provider_type,
            "model": self.model,
            "cost_budget_usd": self.cost_budget_usd,
            "latency_budget_sec": self.latency_budget_sec,
            "fallback_chain": self.fallback_chain,
            "description": self.description,
        }


# MVP primary provider: AST + regex (Week 6 instruction tuning via SKILL.md)
STATIC_AST_PROFILE = ProviderProfile(
    name="static-ast-v1",
    provider_type="static",
    model=None,
    cost_budget_usd=0.0,
    latency_budget_sec=120.0,
    fallback_chain=["regex-only-v1"],
    description="AST-based code analysis + regex doc parsing. No LLM cost.",
)

REGEX_ONLY_PROFILE = ProviderProfile(
    name="regex-only-v1",
    provider_type="static",
    model=None,
    cost_budget_usd=0.0,
    latency_budget_sec=60.0,
    fallback_chain=[],
    description="Fallback: regex-only doc parsing when AST parse fails.",
)

# Post-MVP LLM profile stub (not active)
LLM_DOC_PARSER_STUB = ProviderProfile(
    name="llm-doc-parser-stub",
    provider_type="llm",
    model="gpt-4o-mini",
    cost_budget_usd=0.50,
    latency_budget_sec=30.0,
    fallback_chain=["static-ast-v1", "regex-only-v1"],
    description="TODO Post-MVP: LLM-assisted ambiguous doc parsing.",
)


def get_active_provider() -> ProviderProfile:
    return STATIC_AST_PROFILE


def select_fallback(error_type: str) -> ProviderProfile:
    if error_type == "ast_parse_error":
        return REGEX_ONLY_PROFILE
    return STATIC_AST_PROFILE
