"""LLM 레이어 — 주입 가능한 클라이언트.

설계: 모듈은 LLMClient 프로토콜에만 의존한다. 따라서
  - 테스트/데모: FakeClient (결정적, 네트워크 불필요)
  - 운영: AnthropicClient (Opus/Sonnet/Haiku 라우팅 + prompt caching)
를 동일 인터페이스로 교체할 수 있다.

structured() 는 항상 검증된 pydantic 인스턴스를 반환한다 → 파싱 실패가
타입 레벨에서 차단된다 (docs/artifacts.md 의 계약과 일치).
"""

from __future__ import annotations

import json
import os
from typing import Callable, Protocol, TypeVar

from pydantic import BaseModel

from .cost import cost_for
from .schemas import TokenUsage

T = TypeVar("T", bound=BaseModel)

# 모델 라우팅 (proposal §3) — role → 모델 별칭
MODEL_ROUTING: dict[str, str] = {
    "analysis": "claude-opus-4-8",
    "dialogue": "claude-sonnet-4-6",
    "qcritic": "claude-sonnet-4-6",
    "logging": "claude-haiku-4-5-20251001",
}


class LLMClient(Protocol):
    def structured(
        self, *, role: str, system: str, user: str, schema: type[T]
    ) -> T: ...


class _UsageTracking:
    """API 사용량(토큰) 누적 + 비용 추정. 실제 클라이언트가 상속, FakeClient 는 0 반환."""

    def _init_usage(self) -> None:
        self._usage: dict[str, tuple[int, int]] = {}   # role -> (input, output)
        self._models: dict[str, str] = {}

    def _record(self, role: str, in_tok: int, out_tok: int, model: str) -> None:
        i, o = self._usage.get(role, (0, 0))
        self._usage[role] = (i + in_tok, o + out_tok)
        self._models[role] = model

    def token_usage(self) -> TokenUsage:
        # role 'qcritic' 는 Review 모듈 소속 → review 필드로 합산
        field = {"qcritic": "review"}
        agg = {"analysis": 0, "dialogue": 0, "review": 0, "logging": 0}
        for role, (i, o) in getattr(self, "_usage", {}).items():
            f = field.get(role, role)
            if f in agg:
                agg[f] += i + o
        return TokenUsage(**agg)

    def total_cost(self) -> float:
        total = sum(
            cost_for(self._models.get(role, ""), i, o)
            for role, (i, o) in getattr(self, "_usage", {}).items()
        )
        return round(total, 6)


# --- FakeClient: 결정적 테스트/데모용 -----------------------------------------

FakeHandler = Callable[[str, str, type[BaseModel]], dict | BaseModel]


class FakeClient(_UsageTracking):
    """handler(role, user, schema) -> dict|BaseModel 로 응답을 스크립트한다.

    네트워크·API 키 없이 전체 파이프라인(이중 루프·AND 게이트·Tier 3)을
    E2E 로 검증하기 위한 클라이언트. 토큰/비용은 0 (네트워크 없음).
    """

    def __init__(self, handler: FakeHandler) -> None:
        self._handler = handler
        self.calls: list[tuple[str, str]] = []  # (role, user) 감사 로그
        self._init_usage()

    def structured(self, *, role: str, system: str, user: str, schema: type[T]) -> T:
        self.calls.append((role, user))
        out = self._handler(role, user, schema)
        if isinstance(out, schema):
            return out
        return schema.model_validate(out)


# --- AnthropicClient: 운영용 (선택적) ----------------------------------------

class AnthropicClient(_UsageTracking):
    """실제 Anthropic Messages API. tool-use 로 구조화 출력 강제 + prompt caching.

    anthropic SDK 가 설치되어 있고 ANTHROPIC_API_KEY 가 있을 때만 동작한다.
    """

    def __init__(self, api_key: str | None = None) -> None:
        try:
            import anthropic  # noqa: F401
        except ImportError as e:  # pragma: no cover - 운영 의존성
            raise RuntimeError(
                "anthropic SDK 미설치. `uv pip install anthropic` 또는 FakeClient 사용."
            ) from e
        from anthropic import Anthropic

        self._client = Anthropic(api_key=api_key or os.environ.get("ANTHROPIC_API_KEY"))
        self._init_usage()

    def structured(self, *, role: str, system: str, user: str, schema: type[T]) -> T:  # pragma: no cover - 네트워크
        model = MODEL_ROUTING.get(role, "claude-sonnet-4-6")
        tool = {
            "name": "emit",
            "description": f"{schema.__name__} 스키마로 결과를 반환한다.",
            "input_schema": schema.model_json_schema(),
        }
        resp = self._client.messages.create(
            model=model,
            max_tokens=2048,
            system=[
                # prompt caching: 변하지 않는 시스템 프롬프트를 캐시 (proposal §6 비용)
                {"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}
            ],
            tools=[tool],
            tool_choice={"type": "tool", "name": "emit"},
            messages=[{"role": "user", "content": user}],
        )
        self._record(role, resp.usage.input_tokens, resp.usage.output_tokens, model)
        for block in resp.content:
            if block.type == "tool_use":
                return schema.model_validate(block.input)
        raise RuntimeError("모델이 구조화 출력을 반환하지 않음")


# --- OpenRouterClient: OpenAI 호환 경유로 Claude 호출 (선택적) -----------------

# OpenRouter 는 OpenAI 호환 API 다. 모델 슬러그는 openrouter.ai/models 에서 확인.
# 최신 모델 슬러그가 환경마다 다를 수 있어 단일 모델을 받아 모든 role 에 쓴다(UI 에서 수정 가능).
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
OPENROUTER_DEFAULT_MODEL = "anthropic/claude-sonnet-4.5"


class OpenRouterClient(_UsageTracking):
    """OpenRouter(OpenAI 호환) 경유로 Claude 를 호출한다. tool-calling 으로 구조화 출력 강제.

    openai SDK 가 설치돼 있어야 한다. anthropic SDK 와 달리 base_url 을 OpenRouter 로 돌린다.
    LLMClient 프로토콜을 만족하므로 모듈/오케스트레이터는 그대로 동작한다.
    """

    def __init__(self, api_key: str | None = None, model: str | None = None) -> None:
        try:
            from openai import OpenAI
        except ImportError as e:  # pragma: no cover - 운영 의존성
            raise RuntimeError(
                "openai SDK 미설치. `uv pip install openai` 또는 다른 클라이언트 사용."
            ) from e
        self._client = OpenAI(
            base_url=OPENROUTER_BASE_URL,
            api_key=api_key or os.environ.get("OPENROUTER_API_KEY"),
        )
        self._model = model or OPENROUTER_DEFAULT_MODEL
        self._init_usage()

    def structured(self, *, role: str, system: str, user: str, schema: type[T]) -> T:  # pragma: no cover - 네트워크
        tool = {
            "type": "function",
            "function": {
                "name": "emit",
                "description": f"{schema.__name__} 스키마로 결과를 반환한다.",
                "parameters": schema.model_json_schema(),
            },
        }
        resp = self._client.chat.completions.create(
            model=self._model,
            max_tokens=2048,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            tools=[tool],
            tool_choice={"type": "function", "function": {"name": "emit"}},
        )
        u = getattr(resp, "usage", None)
        if u is not None:
            self._record(
                role,
                getattr(u, "prompt_tokens", 0) or 0,
                getattr(u, "completion_tokens", 0) or 0,
                self._model,
            )
        msg = resp.choices[0].message
        if msg.tool_calls:
            args = json.loads(msg.tool_calls[0].function.arguments)
            return schema.model_validate(args)
        # 일부 모델은 tool_calls 대신 content 에 JSON 을 담기도 함 → 폴백 파싱
        if msg.content:
            return schema.model_validate_json(msg.content)
        raise RuntimeError("모델이 구조화 출력을 반환하지 않음 (OpenRouter)")
