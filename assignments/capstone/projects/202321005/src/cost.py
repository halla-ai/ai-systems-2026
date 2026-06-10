"""토큰 → 비용 추정 (발표용 계산식).

비용 = Σ_role ( 입력토큰/1e6 × 입력단가 + 출력토큰/1e6 × 출력단가 )

**계산식 자체는 정확**하다. 단가(PRICES)는 모델·시점마다 다르므로
발표 시점에 console.anthropic.com / openrouter.ai/models 에서 확인해 수정한다.
토큰 수는 실제 API usage 에서 잡으므로(추정 아님) 신뢰할 수 있다.
"""

from __future__ import annotations

# $ per 1M tokens — (input, output). 발표 시 실제 단가로 갱신할 것.
PRICES: dict[str, tuple[float, float]] = {
    # Anthropic 직접 (src/llm.py MODEL_ROUTING 의 모델 id)
    "claude-opus-4-8": (15.0, 75.0),
    "claude-sonnet-4-6": (3.0, 15.0),
    "claude-haiku-4-5-20251001": (1.0, 5.0),
    # OpenRouter 슬러그 (openrouter.ai/models 에서 정확 단가 확인)
    "anthropic/claude-sonnet-4.5": (3.0, 15.0),
    "anthropic/claude-opus-4.1": (15.0, 75.0),
    "anthropic/claude-haiku-4.5": (1.0, 5.0),
}
DEFAULT_PRICE: tuple[float, float] = (3.0, 15.0)  # 미등록 모델 폴백 (Sonnet 기준)


def cost_for(model: str, in_tok: int, out_tok: int) -> float:
    """모델·토큰 → USD 비용. 미등록 모델은 DEFAULT_PRICE 로 추정."""
    p_in, p_out = PRICES.get(model, DEFAULT_PRICE)
    return in_tok / 1_000_000 * p_in + out_tok / 1_000_000 * p_out
