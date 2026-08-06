"""SocraticTutor — 중앙 집중형 오케스트레이터 (proposal §3.1).

외부 루프(학생 ↔ 시스템) + 내부 루프(Dialogue ↔ Review)의 이중 구조를 조율한다.
아티팩트를 run_dir 에 기록하되 **lab(정답) 은 절대 기록하지 않는다** (INV-1).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from .event_log import EventLog
from .llm import LLMClient
from .modules.analysis import AnalysisModule, load_lab
from .modules.dialogue import DialogueModule
from .modules.logging_mod import LoggingModule
from .modules.review import ReviewModule
from .schemas import (
    ApprovedQuestion,
    DialogueGap,
    HintLevel,
    QuestionDraft,
    ReviewReport,
    SessionState,
    Submission,
    ValidatorRules,
)
from . import validator

# 내부 루프가 학생에게 절대 reject 된 질문을 주지 않도록 하는 안전 폴백
_SAFE_FALLBACK = "지금까지 어떻게 생각했는지 한 단계씩 말해볼 수 있을까요?"


@dataclass
class TurnResult:
    approved: ApprovedQuestion
    retries_used: int
    qcritic_rejects: int
    validator_rejects: int
    context_reset: bool
    reports: list[ReviewReport] = field(default_factory=list)
    judge_rejected: bool = False


class SocraticTutor:
    MAX_RETRY = 3  # Backpressure 임계값 (proposal §3.1)

    def __init__(
        self,
        client: LLMClient,
        run_dir: str | Path = "runs",
        event_log: EventLog | None = None,
    ) -> None:
        self.analysis = AnalysisModule(client)
        self.dialogue = DialogueModule(client)
        self.review = ReviewModule(client)
        self._client = client
        self.run_dir = Path(run_dir)
        # closed-loop event log (append-only, SSOT). 미주입 시 run_dir/event_log.jsonl 로 기록.
        self.events = event_log or EventLog(self.run_dir / "event_log.jsonl")

    # --- 내부 루프 ---------------------------------------------------------

    def _generate_validated(
        self, gap: DialogueGap, rules: ValidatorRules
    ) -> TurnResult:
        feedback: str | None = None
        qcritic_rejects = 0
        validator_rejects = 0
        reports: list[ReviewReport] = []
        drafts: dict[int, QuestionDraft] = {}   # salvage 시 초안의 intended_hint_level 복원용

        for attempt in range(1, self.MAX_RETRY + 1):
            draft = self.dialogue.generate(gap, attempt=attempt, feedback=feedback)
            drafts[attempt] = draft
            self.events.emit(
                "draft_generated", gap.req_id,
                attempt=attempt, intended_hint_level=draft.intended_hint_level,
            )
            report = self.review.check(draft, gap, rules)
            reports.append(report)
            # deterministic gate 판정 기록 (정답·forbidden 원문 X, 매칭 '개수'만 — INV-6)
            self.events.emit(
                "gate_evaluated", gap.req_id,
                attempt=attempt,
                advisory=report.advisory_verdict.result,
                deterministic=report.deterministic_verdict.result,
                final=report.final_verdict,
                matched_forbidden_count=len(report.deterministic_verdict.matched_forbidden),
            )

            if report.final_verdict == "pass":
                approved = ApprovedQuestion(
                    req_id=gap.req_id,
                    text=report.approved_question or draft.text,
                    hint_level=draft.intended_hint_level,
                    retries_used=attempt - 1,
                )
                self.events.emit(
                    "question_approved", gap.req_id,
                    attempt=attempt, hint_level=approved.hint_level,
                    retries_used=approved.retries_used,
                )
                return TurnResult(
                    approved=approved,
                    retries_used=attempt - 1,
                    qcritic_rejects=qcritic_rejects,
                    validator_rejects=validator_rejects,
                    context_reset=False,
                    reports=reports,
                )

            if report.advisory_verdict.result == "reject":
                qcritic_rejects += 1
            if report.deterministic_verdict.result == "reject":
                validator_rejects += 1
            # 다음 시도로 갈 때마다 수위를 낮추고 더 여는 질문으로 유도 → attempt 3 전에 수렴
            feedback = self._augment_feedback(report.retry_hint, attempt)
            if attempt < self.MAX_RETRY:  # 다음 시도가 실제로 있을 때만 (마지막엔 context_reset)
                self.events.emit(
                    "retry_triggered", gap.req_id,
                    from_attempt=attempt, to_attempt=attempt + 1,
                )

        # 재생성 한도 초과 → Context Reset. 무조건 고정 폴백으로 버리지 않고,
        # Validator(안전 게이트)를 통과한 '안전한' 초안이 있으면 그걸 살린다(salvage).
        # Q-Critic(advisory)만 깐 초안은 정답 누출이 없어 학생에게 전달해도 안전하며,
        # 맥락 없는 고정 폴백보다 교육적으로 낫다. 안전 위반(정답 누출) 초안은 절대 살리지 않는다.
        self.events.emit("context_reset", gap.req_id, kind="retry_exhausted")
        approved, salvaged = self._escape(gap, rules, reports, drafts)
        self.events.emit(
            "question_approved", gap.req_id,
            attempt=self.MAX_RETRY, hint_level=approved.hint_level,
            retries_used=approved.retries_used, fallback=True, salvaged=salvaged,
        )
        return TurnResult(
            approved=approved,
            retries_used=self.MAX_RETRY,
            qcritic_rejects=qcritic_rejects,
            validator_rejects=validator_rejects,
            context_reset=True,
            reports=reports,
        )

    @staticmethod
    def _augment_feedback(retry_hint: str | None, attempt: int) -> str:
        """재시도 수렴 유도: 거절될수록 힌트 수위를 낮추고 더 여는(메타인지) 질문으로.

        Dialogue 는 이 문자열을 retry_hint 로 받아 그대로 반영하므로 모듈을 건드리지 않는다."""
        directive = (
            f"[재시도 {attempt + 1}회차] 직전 초안이 게이트에서 거절됐어요. "
            "힌트 수위를 한 단계 낮추고, 계산식·풀이 절차·구체적 행동을 제시하지 말고 "
            "학생이 스스로 떠올리도록 더 여는 질문으로 다시 쓰세요."
        )
        return f"{directive}\n\n[Q-Critic/Validator 피드백]\n{retry_hint or ''}"

    def _escape(
        self,
        gap: DialogueGap,
        rules: ValidatorRules,
        reports: list[ReviewReport],
        drafts: dict[int, QuestionDraft],
    ) -> tuple[ApprovedQuestion, bool]:
        """재시도 소진 후 탈출 질문 선정. (질문, salvaged 여부) 반환.

        Validator 통과(deterministic pass) = 정답 누출 없음 = 학생 전달 안전.
        그중 가장 나중 시도(피드백을 가장 많이 반영한 것)를 살린다. 살릴 게 없으면 고정 폴백."""
        for report in reversed(reports):
            if report.deterministic_verdict.result == "pass":
                draft = drafts.get(report.attempt)
                level: HintLevel = (
                    draft.intended_hint_level if draft
                    else min(3, gap.student_status.allowed_hint_level)  # type: ignore[assignment]
                )
                approved = ApprovedQuestion(
                    req_id=gap.req_id, text=report.question_draft,
                    hint_level=level, retries_used=self.MAX_RETRY,
                )
                return approved, True
        return self._fallback(gap, rules), False

    def _fallback(self, gap: DialogueGap, rules: ValidatorRules) -> ApprovedQuestion:
        # 폴백 질문도 Validator 를 통과해야 한다 (정답 누출 금지)
        text = _SAFE_FALLBACK
        if validator.contains_forbidden(text, rules):
            text = "무엇이 막히는지 한 문장으로 설명해볼 수 있을까요?"
        level: HintLevel = min(3, gap.student_status.allowed_hint_level)  # type: ignore[assignment]
        return ApprovedQuestion(
            req_id=gap.req_id, text=text, hint_level=level, retries_used=self.MAX_RETRY
        )

    # --- 외부 루프 (한 턴) -------------------------------------------------

    def interact(
        self, submission: Submission, state: SessionState, *, aha: bool = False
    ) -> tuple[TurnResult, SessionState]:
        req_id = submission.req_id
        self.events.emit("turn_started", req_id, turn=submission.turn)
        lab = load_lab(submission.lab_id)  # 정답 포함, 메모리 전용 (디스크 재기록 안 함)

        analysis_out = self.analysis.process(submission, state, lab)
        if analysis_out.rejected:
            approved = ApprovedQuestion(
                req_id=req_id,
                text="정답을 그대로 적은 것 같아요. 스스로 한 번 더 풀어볼까요?",
                hint_level=1,
                retries_used=0,
            )
            result = TurnResult(
                approved=approved, retries_used=0, qcritic_rejects=0,
                validator_rejects=0, context_reset=False, judge_rejected=True,
            )
            self.events.emit("judge_aborted", req_id, reason="answer_copied")
            self._emit_turn_committed(req_id, result, aha=aha)
            return result, state

        gap, rules = analysis_out.gap, analysis_out.rules
        assert gap is not None and rules is not None
        self.events.emit(
            "packet_created", req_id,
            artifact="dialogue_gap.json",
            allowed_hint_level=gap.student_status.allowed_hint_level,
        )
        result = self._generate_validated(gap, rules)

        # 아티팩트 기록 (truth 제외)
        self._persist(submission.turn, gap, rules, result)
        self._emit_turn_committed(req_id, result, aha=aha)
        return result, state

    def _emit_turn_committed(self, req_id: str, result: TurnResult, *, aha: bool) -> None:
        """턴 종료 롤업 이벤트. metrics_from_events 가 이 단위를 fold 해 투영한다."""
        self.events.emit(
            "turn_committed", req_id,
            retries_used=result.retries_used,
            hint_level=result.approved.hint_level,
            qcritic_rejects=result.qcritic_rejects,
            validator_rejects=result.validator_rejects,
            context_reset=result.context_reset,
            aha=aha,
        )

    # --- 영속화 (Tier 3: truth 는 절대 쓰지 않음) -------------------------

    def _persist(
        self, turn: int, gap: DialogueGap, rules: ValidatorRules, result: TurnResult
    ) -> None:
        turn_dir = self.run_dir / f"turn_{turn:02d}"
        turn_dir.mkdir(parents=True, exist_ok=True)
        (turn_dir / "dialogue_gap.json").write_text(
            gap.model_dump_json(indent=2), encoding="utf-8"
        )
        (turn_dir / "validator_rules.json").write_text(
            rules.model_dump_json(indent=2), encoding="utf-8"
        )
        if result.reports:
            # 마지막 시도 (artifacts.md 스펙의 review_report.json — 호환 유지)
            (turn_dir / "review_report.json").write_text(
                result.reports[-1].model_dump_json(indent=2), encoding="utf-8"
            )
            # 모든 시도를 시도별로 보존 → 디스크가 event_log/trace 와 완전히 일치 (사후 감사)
            for r in result.reports:
                (turn_dir / f"review_attempt_{r.attempt:02d}.json").write_text(
                    r.model_dump_json(indent=2), encoding="utf-8"
                )
        (turn_dir / "approved_question.json").write_text(
            result.approved.model_dump_json(indent=2), encoding="utf-8"
        )

    def persist_state(self, state: SessionState) -> None:
        """세션 누적 상태를 run_dir 루트에 기록한다 (턴마다 덮어쓰기).

        PATH.md(사람용 전체 기록)와 달리 이 파일은 기계가 읽는 연속성 상태다.
        매 턴 최신 상태로 갱신해 두면 컨텍스트 리셋 후 prior_turns_summary 등을
        다시 주입해 학습 이력을 복원할 수 있다 (truth 는 포함하지 않음, INV-1)."""
        self.run_dir.mkdir(parents=True, exist_ok=True)
        (self.run_dir / "session_state.json").write_text(
            state.model_dump_json(indent=2), encoding="utf-8"
        )


# --- 데모용 결정적 핸들러 + CLI -----------------------------------------------

def _demo_handler(role: str, user: str, schema):
    """API 키 없이 돌아가는 결정적 시나리오 (백프레셔 1회 시연).

    1차 Dialogue 초안은 정답("8명")을 흘려 Validator 가 reject → 재생성 →
    2차 초안은 깨끗 → AND 게이트 통과.
    """
    if role == "analysis":
        return {
            "judge_verdict": "original",
            "student_mistake": "줄어드는 상황인데 덧셈을 함",
            "misconception": "operation_confusion",
            "pedagogical_goal": "학생이 '내리는 것 = 줄어드는 것'을 깨닫고 뺄셈을 떠올리게 한다",
            "forbidden_content": ["8명", "15-7", "15 - 7"],
            "forbidden_nl_patterns": ["정답은 팔", "8명이 남"],
        }
    if role == "dialogue":
        # 재생성 여부를 retry_hint 유무로 판단
        if "retry_hint" in user:
            return {"text": "버스에서 사람이 내리면 버스 안 사람 수는 많아질까요, 적어질까요?", "intended_hint_level": 1}
        # 1차: 정답을 흘리는 나쁜 초안
        return {"text": "15에서 7을 빼면 8명이 남겠죠?", "intended_hint_level": 2}
    if role == "qcritic":
        return {"source": "Q-Critic", "result": "pass", "reasons": []}
    raise ValueError(role)


def main() -> None:  # pragma: no cover - 데모
    from .llm import FakeClient

    client = FakeClient(_demo_handler)
    tutor = SocraticTutor(client, run_dir="runs/demo")
    logger = LoggingModule(session_id="s_demo", lab_id="MATH-01")
    state = SessionState(lab_id="MATH-01", session_id="s_demo", turn=1)

    sub = Submission(
        lab_id="MATH-01", turn=1,
        student_answer="15 더하기 7은 22명이요!",
        student_message="이거 맞아요?", submitted_at="2026-06-01T00:00:00Z",
    )
    result, state = tutor.interact(sub, state)
    print("학생에게 전달된 질문:", result.approved.text)
    print("재생성 횟수:", result.retries_used, "| Validator reject:", result.validator_rejects)

    # gap 은 interact 내부에서 만들어지므로 데모용으로 다시 로드
    gap_path = Path("runs/demo/turn_01/dialogue_gap.json")
    gap = DialogueGap.model_validate_json(gap_path.read_text())
    state = logger.log_turn(
        state, gap, result.approved,
        retries_used=result.retries_used,
        qcritic_rejects=result.qcritic_rejects,
        validator_rejects=result.validator_rejects,
        context_reset=result.context_reset, aha=False,
    )
    tutor.persist_state(state)  # 턴 종료 시 누적 상태를 디스크에 갱신 (연속성/복원용)
    metrics = logger.finalize(cost_usd=0.0)
    Path("runs/demo/PATH.md").write_text(logger.render_path_md(state, metrics), encoding="utf-8")
    Path("runs/demo/metrics.json").write_text(metrics.model_dump_json(indent=2), encoding="utf-8")

    # event_log: closed-loop 의 append-only 기록 + metrics 가 그 투영임을 확인
    from .event_log import EventLog, metrics_from_events

    events = EventLog.load("runs/demo/event_log.jsonl")
    replayed = metrics_from_events(
        events, session_id="s_demo", lab_id="MATH-01", cost_usd=0.0
    )
    print(f"\nevent_log.jsonl: {len(events)} events "
          f"({', '.join(e.event for e in events)})")
    print("metrics == replay(event_log)?", replayed == metrics)

    print("\n--- PATH.md ---")
    print(logger.render_path_md(state, metrics))


if __name__ == "__main__":
    main()
