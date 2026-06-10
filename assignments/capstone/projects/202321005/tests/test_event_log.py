"""event_log.jsonl 검증 (INV-6, docs/artifacts.md §2 (7)).

닫힌 루프의 append-only 이벤트 로그가
  ① seq 가 빈틈없이 1부터 증가하고(append 순서 보존),
  ② 정답·forbidden 원문을 값으로 담지 않으며(Tier 3 유지),
  ③ replay(fold)한 metrics 가 LoggingModule.finalize() 와 일치(=투영, 결정적)
하는지 본다.
"""

from __future__ import annotations

from src.event_log import EventLog, metrics_from_events
from src.llm import FakeClient
from src.modules.logging_mod import LoggingModule
from src.orchestrator import SocraticTutor
from src.schemas import DialogueGap, SessionState, Submission


def _sub(turn: int = 1) -> Submission:
    return Submission(
        lab_id="MATH-01", turn=turn,
        student_answer="15 더하기 7은 22명이요!",
        student_message="이거 맞아요?", submitted_at="2026-06-01T00:00:00Z",
    )


def _run_one_turn(fake_client, run_dir):
    """한 턴(백프레셔 1회 포함)을 돌리고 (event_log 경로, LoggingModule metrics) 반환."""
    tutor = SocraticTutor(fake_client, run_dir=run_dir)
    logger = LoggingModule(session_id="s", lab_id="MATH-01")
    state = SessionState(lab_id="MATH-01", session_id="s", turn=1)

    result, state = tutor.interact(_sub(), state)
    gap = DialogueGap.model_validate_json(
        (run_dir / "turn_01" / "dialogue_gap.json").read_text()
    )
    logger.log_turn(
        state, gap, result.approved,
        retries_used=result.retries_used,
        qcritic_rejects=result.qcritic_rejects,
        validator_rejects=result.validator_rejects,
        context_reset=result.context_reset, aha=False,
    )
    return run_dir / "event_log.jsonl", logger.finalize(cost_usd=0.0)


def test_seq_is_gapless_and_ordered(fake_client, tmp_path):
    log_path, _ = _run_one_turn(fake_client, tmp_path)
    events = EventLog.load(log_path)

    assert events, "이벤트가 하나도 기록되지 않았다"
    assert [e.seq for e in events] == list(range(1, len(events) + 1))
    assert events[0].event == "turn_started"
    assert events[-1].event == "turn_committed"
    # 닫힌 루프 형태: 적어도 gate 판정과 재생성이 기록돼야 함
    kinds = {e.event for e in events}
    assert {"packet_created", "draft_generated", "gate_evaluated",
            "retry_triggered", "question_approved"} <= kinds


def test_no_answer_strings_in_log(fake_client, tmp_path):
    """INV-6: 로그 어디에도 정답·forbidden 원문이 값으로 남지 않는다 (grep)."""
    log_path, _ = _run_one_turn(fake_client, tmp_path)
    raw = log_path.read_text(encoding="utf-8")

    for needle in ("reference_solution", "8명", "15-7", "15 - 7"):
        assert needle not in raw, f"event_log 에 금지 문자열 '{needle}' 누출"


def test_metrics_is_projection_of_event_log(fake_client, tmp_path):
    """replay(event_log)로 재구성한 metrics 가 LoggingModule.finalize() 와 동일."""
    log_path, logged_metrics = _run_one_turn(fake_client, tmp_path)
    events = EventLog.load(log_path)

    replayed = metrics_from_events(
        events, session_id="s", lab_id="MATH-01", cost_usd=0.0
    )
    assert replayed == logged_metrics

    # 세부 gate 이벤트의 reject 합도 롤업 수치와 교차 검증된다
    det_rejects = sum(
        1 for e in events
        if e.event == "gate_evaluated" and e.data["deterministic"] == "reject"
    )
    assert det_rejects == replayed.validator_reject_count


def test_failure_path_is_recorded(tmp_path):
    """재생성 한도 초과(안전 실패) 경로가 event_log 에 그대로 남는다."""

    def always_leak(role, user, schema):
        if role == "analysis":
            return {
                "judge_verdict": "original", "student_mistake": "줄어드는데 더함",
                "misconception": "operation_confusion", "pedagogical_goal": "g",
                "forbidden_content": ["8명"], "forbidden_nl_patterns": [],
            }
        if role == "dialogue":
            return {"text": "그러면 8명이 남겠죠?", "intended_hint_level": 2}
        if role == "qcritic":
            return {"source": "Q-Critic", "result": "pass", "reasons": []}
        raise ValueError(role)

    tutor = SocraticTutor(FakeClient(always_leak), run_dir=tmp_path)
    state = SessionState(lab_id="MATH-01", session_id="s", turn=1)
    tutor.interact(_sub(), state)

    events = EventLog.load(tmp_path / "event_log.jsonl")
    kinds = [e.event for e in events]
    assert "context_reset" in kinds            # 안전 실패가 기록됨
    assert kinds.count("retry_triggered") == tutor.MAX_RETRY - 1
    reset = next(e for e in events if e.event == "context_reset")
    assert reset.data["kind"] == "retry_exhausted"
