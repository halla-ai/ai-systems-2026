"""Validator — Deterministic(hard) 센서. 순수 코드, LLM 미사용.

Review Module 의 두 센서 중 규칙 기반 쪽. forbidden_content / nl_patterns / markers 를
매칭해 정답(숫자·식) 유출을 차단한다. 실패 모드는 우회 가능(False Positive 적음)이며,
Q-Critic(Advisory)이 보완한다 (proposal §2.1.2, §2.3.4).

이 모듈은 `.claude/agents/` 에 .md 가 없다 — 프롬프트가 아니라 코드이기 때문이다(D-5).
"""

from __future__ import annotations

import re

from .schemas import DeterministicVerdict, ValidatorRules

_WS = re.compile(r"\s+")


def _normalize_code(s: str) -> str:
    """공백 제거 + 소문자화. `15 - 7` 과 `15-7` 을 같은 것으로 본다.

    하드 게이트는 과탐(over-block)이 미탐보다 안전하므로 공격적으로 정규화한다.
    """
    return _WS.sub("", s).lower()


def _normalize_nl(s: str) -> str:
    """자연어: 연속 공백만 단일화."""
    return _WS.sub(" ", s).strip().lower()


def contains_forbidden(text: str, rules: ValidatorRules) -> list[str]:
    """text 에 포함된 금지 항목 목록을 반환한다 (없으면 빈 리스트).

    Validator 본판정과 retry_hint 재검증(INV-5)에 공통 사용된다.
    """
    matched: list[str] = []
    code_text = _normalize_code(text)
    nl_text = _normalize_nl(text)

    for marker in rules.forbidden_markers:
        if marker and marker in text:  # 추가 차단 마커는 원문 그대로 검사
            matched.append(marker)

    for forbidden in rules.forbidden_content:  # 정답 숫자·식 (공백 무시 매칭)
        if _normalize_code(forbidden) in code_text:
            matched.append(forbidden)

    for pattern in rules.forbidden_nl_patterns:
        if _normalize_nl(pattern) in nl_text:
            matched.append(pattern)

    return matched


def evaluate(question_text: str, rules: ValidatorRules) -> DeterministicVerdict:
    """질문 초안에 대한 Deterministic 판정."""
    matched = contains_forbidden(question_text, rules)
    return DeterministicVerdict(
        result="reject" if matched else "pass",
        matched_forbidden=matched,
    )
