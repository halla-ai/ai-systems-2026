"""Validator (결정적 센서) 단위 테스트."""

from __future__ import annotations

from src import validator
from src.schemas import ValidatorRules


def _rules(**kw):
    base = dict(
        req_id="MATH-01-t01",
        forbidden_content=["8명", "15-7", "15 - 7"],
        forbidden_nl_patterns=["정답은 팔"],
    )
    base.update(kw)
    return ValidatorRules(**base)


def test_clean_question_passes():
    v = validator.evaluate("사람이 내리면 수는 어떻게 될까요?", _rules())
    assert v.result == "pass"
    assert v.matched_forbidden == []


def test_forbidden_answer_rejected():
    v = validator.evaluate("그러면 8명이 남아요.", _rules())
    assert v.result == "reject"
    assert "8명" in v.matched_forbidden


def test_whitespace_variation_still_caught():
    """`15 - 7` 처럼 공백이 들어가도 `15-7` 로 정규화 매칭."""
    v = validator.evaluate("그럼 15 - 7 을 계산하면 되나요?", _rules())
    assert v.result == "reject"


def test_korean_bypass_pattern_caught():
    v = validator.evaluate("그러니까 정답은 팔이겠죠?", _rules())
    assert v.result == "reject"


def test_explicit_marker_caught():
    """forbidden_markers 로 지정한 마커는 원문 그대로 차단된다."""
    v = validator.evaluate("[정답] 8", _rules(forbidden_markers=["[정답]"]))
    assert v.result == "reject"
    assert "[정답]" in v.matched_forbidden


def test_contains_forbidden_reused_for_retry_hint():
    """retry_hint 재검증(INV-5)에 쓰이는 함수가 동일하게 동작."""
    assert validator.contains_forbidden("8명이라고 말해줘", _rules())
    assert not validator.contains_forbidden("더 쉬운 말로 다시 물어보라", _rules())
