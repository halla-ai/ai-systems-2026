"""E2E: FakeClient 로 전체 이중 루프(백프레셔 포함)를 검증한다."""

from __future__ import annotations

from src.llm import FakeClient
from src.modules.analysis import AnalysisModule, load_lab
from src.orchestrator import SocraticTutor
from src.schemas import SessionState, Submission


def _sub(turn=1):
    return Submission(
        lab_id="MATH-01", turn=turn,
        student_answer="15 더하기 7은 22명이요!",
        student_message="이거 맞아요?", submitted_at="2026-06-01T00:00:00Z",
    )


def test_backpressure_then_clean_question(fake_client, tmp_path):
    tutor = SocraticTutor(fake_client, run_dir=tmp_path)
    state = SessionState(lab_id="MATH-01", session_id="s", turn=1)

    result, _ = tutor.interact(_sub(), state)

    # 1차 초안이 정답을 흘려 reject → 재생성 1회 → 통과
    assert result.retries_used == 1
    assert result.validator_rejects == 1
    assert result.context_reset is False
    # 학생에게 전달된 질문은 정답을 포함하지 않는다
    assert "8명" not in result.approved.text
    assert "15-7" not in result.approved.text.replace(" ", "")


def test_never_delivers_rejected_question_even_when_exhausted(tmp_path):
    """Dialogue 가 매번 정답을 흘려도, 학생에게 가는 질문은 항상 깨끗하다."""

    def always_leak(role, user, schema):
        if role == "analysis":
            return {
                "judge_verdict": "original",
                "student_mistake": "줄어드는데 더함",
                "misconception": "operation_confusion",
                "pedagogical_goal": "g",
                "forbidden_content": ["8명"], "forbidden_nl_patterns": [],
            }
        if role == "dialogue":
            return {"text": "그러면 8명이 남겠죠?", "intended_hint_level": 2}
        if role == "qcritic":
            return {"source": "Q-Critic", "result": "pass", "reasons": []}
        raise ValueError(role)

    tutor = SocraticTutor(FakeClient(always_leak), run_dir=tmp_path)
    state = SessionState(lab_id="MATH-01", session_id="s", turn=1)
    result, _ = tutor.interact(_sub(), state)

    assert result.context_reset is True          # 재생성 한도 초과 → 리셋
    assert result.validator_rejects == tutor.MAX_RETRY
    assert "8명" not in result.approved.text      # 폴백은 깨끗


def test_judge_blocks_copied_answer(tmp_path):
    """정답을 베껴 적으면 Judge 가 파이프라인을 중단한다."""

    def copied(role, user, schema):
        if role == "analysis":
            return {
                "judge_verdict": "copied", "student_mistake": "none",
                "misconception": "operation_confusion", "pedagogical_goal": "g",
                "forbidden_content": [], "forbidden_nl_patterns": [],
            }
        raise AssertionError("copied 면 Dialogue/Review 가 호출되면 안 됨")

    tutor = SocraticTutor(FakeClient(copied), run_dir=tmp_path)
    state = SessionState(lab_id="MATH-01", session_id="s", turn=1)
    result, _ = tutor.interact(_sub(), state)
    assert result.judge_rejected is True


def test_planner_outputs_split_into_two_artifacts(fake_client):
    """Analysis 가 정답 0 인 gap 과 forbidden 을 담은 rules 를 분리 생성한다 (D-1)."""
    lab = load_lab("MATH-01")
    state = SessionState(lab_id="MATH-01", session_id="s", turn=1)
    out = AnalysisModule(fake_client).process(_sub(), state, lab)

    assert out.gap is not None and out.rules is not None
    # gap 에는 forbidden 이 없고, rules 에만 있다
    assert "forbidden_content" not in out.gap.model_dump()
    assert out.rules.forbidden_content  # 비어있지 않음
    assert out.gap.req_id == out.rules.req_id  # INV-4
