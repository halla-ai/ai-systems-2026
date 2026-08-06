"""INV-2/3: Dialogue 가 보는 데이터에 정답 파생 키가 부재함을 강제.

§6 절대 기준 "Tier 3 구조적 누출 0건" 을 코드로 검증한다.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.schemas import (
    TIER3_FORBIDDEN_KEYS,
    DialogueGap,
    StudentStatus,
)


def _valid_gap_kwargs():
    return dict(
        req_id="MATH-01-t04",
        student_status=StudentStatus(
            student_mistake="줄어드는 상황인데 덧셈을 함",
            misconception="operation_confusion",
            iteration_count=4,
            last_hint_level=2,
            allowed_hint_level=2,
        ),
        pedagogical_goal="g",
    )


def test_dialogue_gap_has_no_forbidden_fields():
    """DialogueGap 모델 필드 집합에 금지 키가 아예 존재하지 않는다."""
    fields = set(DialogueGap.model_fields)
    assert TIER3_FORBIDDEN_KEYS.isdisjoint(fields), (
        f"DialogueGap 에 금지 필드 존재: {TIER3_FORBIDDEN_KEYS & fields}"
    )


@pytest.mark.parametrize("forbidden_key", sorted(TIER3_FORBIDDEN_KEYS))
def test_dialogue_gap_rejects_forbidden_injection(forbidden_key):
    """금지 키를 외부에서 주입하면 extra='forbid' 가 거부한다."""
    with pytest.raises(ValidationError):
        DialogueGap(**_valid_gap_kwargs(), **{forbidden_key: "8명"})


def test_dialogue_gap_dump_has_no_forbidden_keys():
    """직렬화 결과(JSON)에도 금지 키가 없다."""
    gap = DialogueGap(**_valid_gap_kwargs())
    dumped = gap.model_dump()
    flat = set(dumped) | set(dumped["student_status"])
    assert TIER3_FORBIDDEN_KEYS.isdisjoint(flat)
