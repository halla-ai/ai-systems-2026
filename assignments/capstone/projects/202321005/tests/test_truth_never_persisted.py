"""INV-1: reference_solution(정답) 이 공유 아티팩트 디렉토리에 절대 기록되지 않는다.

orchestrator 를 한 턴 돌린 뒤 run_dir 전체를 grep 하여 정답 원문 부재를 검증한다.
"""

from __future__ import annotations

from src.modules.analysis import load_lab
from src.orchestrator import SocraticTutor
from src.schemas import SessionState, Submission


def test_reference_solution_absent_from_run_dir(fake_client, tmp_path):
    lab = load_lab("MATH-01")
    tutor = SocraticTutor(fake_client, run_dir=tmp_path)
    state = SessionState(lab_id="MATH-01", session_id="s_test", turn=1)
    sub = Submission(
        lab_id="MATH-01", turn=1,
        student_answer="15 더하기 7은 22명이요!",
        student_message="이거 맞아요?", submitted_at="2026-06-01T00:00:00Z",
    )

    tutor.interact(sub, state)

    written = list(tmp_path.rglob("*"))
    assert written, "아티팩트가 하나도 기록되지 않음 (테스트 전제 실패)"

    ref = lab["reference_solution"]  # "15 - 7 = 8, 답은 8명"
    for f in tmp_path.rglob("*"):
        if f.is_file():
            text = f.read_text(encoding="utf-8")
            assert ref not in text, f"INV-1 위반: {f} 에 정답 원문이 기록됨"


def test_forbidden_keys_absent_from_dialogue_gap_artifact(fake_client, tmp_path):
    """디스크에 기록된 dialogue_gap.json 에 금지 키가 없다 (INV-2)."""
    from src.schemas import TIER3_FORBIDDEN_KEYS

    tutor = SocraticTutor(fake_client, run_dir=tmp_path)
    state = SessionState(lab_id="MATH-01", session_id="s_test", turn=1)
    sub = Submission(
        lab_id="MATH-01", turn=1, student_answer="22명",
        submitted_at="2026-06-01T00:00:00Z",
    )
    tutor.interact(sub, state)

    gap_file = tmp_path / "turn_01" / "dialogue_gap.json"
    text = gap_file.read_text(encoding="utf-8")
    for key in TIER3_FORBIDDEN_KEYS:
        assert f'"{key}"' not in text, f"dialogue_gap.json 에 금지 키 {key} 존재"
