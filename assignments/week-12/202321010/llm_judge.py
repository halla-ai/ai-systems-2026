"""
llm_judge.py
------------
Strict-JSON LLM Judge.

실행 모드
  mock  : 실제 API 없이 결정론적 휴리스틱 기반 평가
          (길이 편향 등 LLM 편향을 의도적으로 재현)
  api   : OPENAI_API_KEY 환경 변수가 있을 때 실제 GPT 호출

반환 스키마 (항상 엄격한 JSON)
  {
    "sample_id"    : int,
    "correctness"  : float,   # 0-10
    "efficiency"   : float,   # 0-10
    "readability"  : float,   # 0-10
    "security"     : float,   # 0-10
    "overall"      : float,   # 0-10  (weighted average)
    "issues"       : [str],
    "strengths"    : [str],
    "reasoning"    : str,
    "mode"         : "mock" | "api"
  }
"""

from __future__ import annotations

import ast
import json
import os
import re
import textwrap
from dataclasses import asdict, dataclass, field
from typing import Any


# ─────────────────────────────────────────────────────────────────────────────
# 출력 스키마
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class JudgeResult:
    sample_id: int
    correctness: float
    efficiency: float
    readability: float
    security: float
    overall: float
    issues: list[str]
    strengths: list[str]
    reasoning: str
    mode: str

    def to_strict_json(self) -> str:
        """strict JSON 문자열 반환 – 항상 파싱 가능하도록 보장."""
        d = asdict(self)
        # 숫자는 소수점 1자리로 고정
        for key in ("correctness", "efficiency", "readability", "security", "overall"):
            d[key] = round(float(d[key]), 1)
        return json.dumps(d, ensure_ascii=False, indent=2)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "JudgeResult":
        return cls(**{k: d[k] for k in cls.__dataclass_fields__})


# ─────────────────────────────────────────────────────────────────────────────
# JSON 스키마 검증
# ─────────────────────────────────────────────────────────────────────────────

REQUIRED_KEYS = {
    "sample_id": int,
    "correctness": (int, float),
    "efficiency": (int, float),
    "readability": (int, float),
    "security": (int, float),
    "overall": (int, float),
    "issues": list,
    "strengths": list,
    "reasoning": str,
    "mode": str,
}


def _validate_schema(d: dict) -> None:
    """스키마 위반 시 ValueError 를 올림."""
    for key, expected_type in REQUIRED_KEYS.items():
        if key not in d:
            raise ValueError(f"Missing required key: '{key}'")
        if not isinstance(d[key], expected_type):
            raise ValueError(
                f"Key '{key}': expected {expected_type}, got {type(d[key])}"
            )
    for score_key in ("correctness", "efficiency", "readability", "security", "overall"):
        val = float(d[score_key])
        if not (0.0 <= val <= 10.0):
            raise ValueError(f"Score '{score_key}' out of range [0, 10]: {val}")


# ─────────────────────────────────────────────────────────────────────────────
# Mock 평가 엔진
# (의도적 편향 포함 – 아래 Notes 참조)
#
# 관찰된 편향 #1: Length Bias
#   줄 수가 많을수록 readability 와 overall 을 과도하게 높게 부여.
#   Sample 5(장황)는 실제보다 높게, Sample 6(간결)은 낮게 평가됨.
# ─────────────────────────────────────────────────────────────────────────────

# 사전 결정된 mock 점수 테이블
# (실제 LLM 이 보일 법한 편향을 포함하여 수동으로 설계)
_MOCK_SCORES: dict[int, dict] = {
    1:  dict(correctness=9.0, efficiency=8.5, readability=8.5, security=9.0,
             issues=[],
             strengths=["명확한 루프 불변식", "O(log n) 시간복잡도", "타입 힌트 사용"],
             reasoning="표준적인 이진 탐색 구현으로 정확하고 효율적입니다."),
    2:  dict(correctness=8.0, efficiency=4.0, readability=7.0, security=8.0,
             issues=["정렬된 배열에서도 O(n²) 수행", "조기 종료 플래그 없음"],
             strengths=["구현 자체는 정확"],
             reasoning="동작은 하나 최악의 경우를 피할 조기 종료가 없습니다."),
    3:  dict(correctness=6.0, efficiency=6.0, readability=6.5, security=3.0,
             issues=["SQL 인젝션 취약점: 사용자 입력 직접 삽입"],
             strengths=["sqlite3 표준 라이브러리 사용"],
             reasoning="기능은 동작하지만 파라미터화 쿼리를 사용하지 않아 보안 위험이 높습니다."),
    4:  dict(correctness=2.5, efficiency=7.0, readability=6.5, security=8.0,
             issues=["off-by-one: range(len-1) 로 인해 마지막 원소 누락"],
             strengths=["간단한 구조"],
             reasoning="명백한 off-by-one 버그가 있습니다."),
    # ── 길이 편향 발현: Sample 5는 실제보다 높게 평가됨 ──
    5:  dict(correctness=8.5, efficiency=6.0, readability=9.0, security=8.5,
             issues=["loop 대신 sum() 내장 함수 사용 권장"],
             strengths=["상세한 docstring", "단계별 주석", "빈 리스트 처리"],
             reasoning="충분한 문서화와 명확한 단계별 구현으로 가독성이 매우 높습니다."
                       " (주석이 풍부하여 높은 점수를 부여)"),
    # ── 길이 편향 발현: Sample 6은 실제보다 낮게 평가됨 ──
    6:  dict(correctness=8.0, efficiency=9.0, readability=5.5, security=8.0,
             issues=["주석 부족", "코드 설명이 불충분"],
             strengths=["sum() 내장 함수 활용", "타입 힌트"],
             reasoning="기능적으로 정확하지만 주석과 설명이 부족합니다."
                       " 더 긴 설명이 있으면 좋겠습니다."),
    7:  dict(correctness=7.5, efficiency=7.0, readability=5.0, security=8.0,
             issues=["unused_counter 미사용 변수", "의미 없는 else-pass", "도달 불가 코드"],
             strengths=["빈 리스트 경계 처리"],
             reasoning="동작은 하지만 사문 코드가 유지보수를 어렵게 합니다."),
    8:  dict(correctness=7.0, efficiency=7.0, readability=6.5, security=2.5,
             issues=["DB_PASSWORD 하드코딩", "API_KEY 소스코드 노출"],
             strengths=["f-string 사용"],
             reasoning="보안 민감 정보가 소스코드에 직접 포함되어 있습니다."),
    9:  dict(correctness=0.5, efficiency=1.0, readability=1.5, security=5.0,
             issues=["SyntaxError: 함수 정의 콜론 누락", "if 문 콜론 누락", "NameError: reslt"],
             strengths=[],
             reasoning="파이썬 문법 오류가 다수 있어 실행 자체가 불가합니다."),
    10: dict(correctness=8.0, efficiency=6.5, readability=5.5, security=8.5,
             issues=["단순 덧셈에 Factory+Strategy 패턴은 과도한 설계"],
             strengths=["타입 힌트", "레지스트리 패턴 올바르게 구현"],
             reasoning="동작은 하지만 불필요한 추상화 레이어가 복잡도를 높입니다."),
}

# overall 가중치
_W = dict(correctness=0.35, efficiency=0.25, readability=0.20, security=0.20)


def _compute_overall(s: dict) -> float:
    return round(
        sum(_W[k] * s[k] for k in _W),
        1,
    )


def _mock_evaluate(sample_id: int, code: str) -> dict:
    """Mock 평가 – 사전 정의된 점수 테이블 반환."""
    if sample_id not in _MOCK_SCORES:
        raise ValueError(f"Unknown sample_id: {sample_id}")
    s = dict(_MOCK_SCORES[sample_id])
    s["sample_id"] = sample_id
    s["overall"] = _compute_overall(s)
    s["mode"] = "mock"
    return s


# ─────────────────────────────────────────────────────────────────────────────
# API 평가 엔진 (OpenAI)
# ─────────────────────────────────────────────────────────────────────────────

_SYSTEM_PROMPT = textwrap.dedent("""\
    당신은 코드 품질 평가 전문가입니다.
    아래 Python 코드를 분석하고 반드시 다음 JSON 스키마만 반환하십시오.
    추가 텍스트나 마크다운 코드블록은 절대 포함하지 마십시오.

    JSON 스키마:
    {
      "sample_id": <int>,
      "correctness": <0-10 float>,
      "efficiency":  <0-10 float>,
      "readability": <0-10 float>,
      "security":    <0-10 float>,
      "overall":     <0-10 float>,
      "issues":      [<string>, ...],
      "strengths":   [<string>, ...],
      "reasoning":   "<string>",
      "mode":        "api"
    }

    평가 기준:
    - correctness : 코드가 의도한 대로 올바르게 동작하는가
    - efficiency  : 시간/공간 복잡도가 적절한가
    - readability : 명명, 구조, 주석의 명확성
    - security    : 보안 취약점 (인젝션, 하드코딩 자격증명, 입력 검증 등)
    - overall     : correctness*0.35 + efficiency*0.25 + readability*0.20 + security*0.20
    - 코드 길이 자체는 점수에 영향을 주지 않도록 하십시오.
""")


def _api_evaluate(sample_id: int, code: str) -> dict:
    """OpenAI API 를 통한 실제 LLM 평가."""
    try:
        from openai import OpenAI
    except ImportError:
        raise RuntimeError("openai 패키지가 설치되지 않았습니다: pip install openai")

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY 환경 변수가 설정되지 않았습니다.")

    client = OpenAI(api_key=api_key)
    user_msg = f"sample_id: {sample_id}\n\n```python\n{code}\n```"

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user",   "content": user_msg},
        ],
        temperature=0.0,         # 결정론적 출력
        response_format={"type": "json_object"},
    )
    raw = response.choices[0].message.content
    return json.loads(raw)


# ─────────────────────────────────────────────────────────────────────────────
# 공개 인터페이스
# ─────────────────────────────────────────────────────────────────────────────

class LLMJudge:
    """
    코드 샘플을 평가하고 strict JSON 을 반환하는 Judge.

    Parameters
    ----------
    mode : "auto" | "mock" | "api"
        "auto" 는 OPENAI_API_KEY 가 있으면 api, 없으면 mock 을 사용.
    """

    def __init__(self, mode: str = "auto") -> None:
        if mode == "auto":
            try:
                import openai as _openai_check  # noqa: F401
                _openai_available = True
            except ImportError:
                _openai_available = False
            self._mode = (
                "api" if (_openai_available and os.environ.get("OPENAI_API_KEY"))
                else "mock"
            )
        elif mode in ("mock", "api"):
            self._mode = mode
        else:
            raise ValueError(f"mode 는 'auto', 'mock', 'api' 중 하나여야 합니다: {mode}")

    # ──────────────────────────────────────────────
    def evaluate(self, sample_id: int, code: str) -> JudgeResult:
        """
        코드를 평가하고 JudgeResult 를 반환.
        내부적으로 strict JSON 을 거쳐 스키마를 검증함.
        """
        if self._mode == "api":
            raw_dict = _api_evaluate(sample_id, code)
        else:
            raw_dict = _mock_evaluate(sample_id, code)

        # ── Strict JSON 직렬화 → 파싱 왕복으로 무결성 보장 ──
        json_str = json.dumps(raw_dict, ensure_ascii=False)
        parsed   = json.loads(json_str)

        _validate_schema(parsed)

        result = JudgeResult.from_dict(parsed)
        return result

    def evaluate_all(self, samples: list[dict]) -> list[JudgeResult]:
        """샘플 목록 전체를 순차 평가."""
        return [self.evaluate(s["id"], s["code"]) for s in samples]
