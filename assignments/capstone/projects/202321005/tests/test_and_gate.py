"""AND 게이트 진리표: (advisory, deterministic) → final."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.schemas import AdvisoryVerdict, DeterministicVerdict, ReviewReport


def _build(adv: str, det: str, final: str):
    kw = dict(
        req_id="MATH-01-t01",
        attempt=1,
        question_draft="q",
        advisory_verdict=AdvisoryVerdict(result=adv, reasons=["r"] if adv == "reject" else []),
        deterministic_verdict=DeterministicVerdict(result=det),
        final_verdict=final,
    )
    if final == "pass":
        kw["approved_question"] = "q"
    else:
        kw["retry_hint"] = "추상화하라"
    return ReviewReport(**kw)


@pytest.mark.parametrize(
    "adv,det,expected",
    [
        ("pass", "pass", "pass"),
        ("pass", "reject", "reject"),
        ("reject", "pass", "reject"),
        ("reject", "reject", "reject"),
    ],
)
def test_and_truth_table(adv, det, expected):
    report = _build(adv, det, expected)
    assert report.final_verdict == expected


@pytest.mark.parametrize(
    "adv,det,wrong_final",
    [
        ("pass", "pass", "reject"),
        ("pass", "reject", "pass"),
        ("reject", "pass", "pass"),
    ],
)
def test_inconsistent_final_rejected(adv, det, wrong_final):
    """AND 결과와 불일치하는 final_verdict 는 모델이 거부한다."""
    with pytest.raises(ValidationError):
        _build(adv, det, wrong_final)


def test_pass_requires_approved_question():
    with pytest.raises(ValidationError):
        ReviewReport(
            req_id="x", attempt=1, question_draft="q",
            advisory_verdict=AdvisoryVerdict(result="pass"),
            deterministic_verdict=DeterministicVerdict(result="pass"),
            final_verdict="pass",  # approved_question 누락
        )


def test_reject_requires_retry_hint():
    with pytest.raises(ValidationError):
        ReviewReport(
            req_id="x", attempt=1, question_draft="q",
            advisory_verdict=AdvisoryVerdict(result="reject", reasons=["r"]),
            deterministic_verdict=DeterministicVerdict(result="pass"),
            final_verdict="reject",  # retry_hint 누락
        )
