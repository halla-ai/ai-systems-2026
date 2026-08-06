"""스키마 라운드트립 + extra='forbid' 검증."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.schemas import (
    ApprovedQuestion,
    DialogueGap,
    Metrics,
    SessionState,
    StudentStatus,
    Submission,
    ValidatorRules,
    make_req_id,
)


def test_req_id_format():
    assert make_req_id("MATH-01", 4) == "MATH-01-t04"
    assert make_req_id("MATH-01", 12) == "MATH-01-t12"


def test_dialogue_gap_roundtrip():
    gap = DialogueGap(
        req_id="MATH-01-t04",
        student_status=StudentStatus(
            student_mistake="줄어드는데 더함", misconception="operation_confusion",
            iteration_count=4, last_hint_level=2, allowed_hint_level=2,
        ),
        pedagogical_goal="g",
    )
    again = DialogueGap.model_validate_json(gap.model_dump_json())
    assert again == gap


def test_extra_key_forbidden():
    with pytest.raises(ValidationError):
        ValidatorRules(req_id="x", forbidden_content=[], surprise=1)


def test_hint_level_out_of_range_rejected():
    with pytest.raises(ValidationError):
        StudentStatus(
            student_mistake="m", misconception="m", iteration_count=0,
            last_hint_level=2, allowed_hint_level=4,  # 4 는 허용 밖
        )


def test_submission_req_id_property():
    sub = Submission(
        lab_id="MATH-01", turn=3, student_answer="22명", submitted_at="2026-06-01T00:00:00Z"
    )
    assert sub.req_id == "MATH-01-t03"


def test_metrics_and_state_roundtrip():
    m = Metrics(session_id="s", lab_id="MATH-01", total_turns=2)
    assert Metrics.model_validate_json(m.model_dump_json()) == m
    s = SessionState(lab_id="MATH-01", session_id="s", turn=1)
    assert SessionState.model_validate_json(s.model_dump_json()) == s
