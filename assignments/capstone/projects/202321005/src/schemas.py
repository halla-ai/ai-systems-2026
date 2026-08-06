"""Single source of truth for the Socratic Tutor artifact contract.

모든 모듈 간 JSON은 여기 정의된 pydantic v2 모델의 직렬화 결과다.
계약 문서: ../docs/artifacts.md  (필드/불변식은 그 문서와 1:1로 일치해야 한다)

Tier 3 불변식 (docs/artifacts.md §0):
  INV-1  reference_solution 은 lab dict(메모리)에만 존재. 공유 디렉토리에 직렬화 금지.
  INV-2  forbidden_content 는 DialogueGap 에 *필드로 존재하지 않는다* → 타입 레벨 보장.
  INV-3  DialogueGap 의 키 집합은 폐쇄(extra="forbid"). 금지 키 주입 시 즉시 ValidationError.
  INV-4  한 턴의 모든 아티팩트는 동일 req_id 로 묶인다 (make_req_id).
  INV-5  retry_hint 는 reject 일 때만 존재.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

# --- 공통 타입 ----------------------------------------------------------------

HintLevel = Literal[0, 1, 2, 3]   # 0=None(최초턴), 1=Concept, 2=Logic, 3=Scaffolding
Verdict = Literal["pass", "reject"]


class Artifact(BaseModel):
    """모든 아티팩트의 베이스. 미정의 키를 거부해 계약을 폐쇄한다(INV-3)."""

    model_config = ConfigDict(extra="forbid")


def make_req_id(lab_id: str, turn: int) -> str:
    """INV-4: 한 턴의 모든 아티팩트를 묶는 상관관계 ID."""
    return f"{lab_id}-t{turn:02d}"


# --- (0) submission ----------------------------------------------------------

class Submission(Artifact):
    lab_id: str
    turn: int = Field(ge=1)
    student_answer: str
    student_message: str | None = None
    submitted_at: str  # ISO8601, 호출측 주입 (Date.now 비결정성 회피)

    @property
    def req_id(self) -> str:
        return make_req_id(self.lab_id, self.turn)


# --- (T) 정답 영역 = lab dict ------------------------------------------------
# 정답(reference_solution 포함)은 labs/<lab>.json 을 load_lab() 로 읽은 raw dict 로
# Analysis 메모리에만 존재한다. 별도 pydantic 모델로 감싸지 않는다(단순화).
# 디스크에는 다시 기록하지 않으므로(orchestrator._persist 가 lab 을 쓰지 않음) INV-1 이 유지되고,
# test_truth_never_persisted 가 grep 으로 검증한다.


# --- (1a) dialogue_gap.json  — Dialogue + Q-Critic 가 읽음 (정답 0, INV-2) -----

class StudentStatus(Artifact):
    student_mistake: str                          # 관찰된 실수 유형만 (학생 답안 원문 X)
    misconception: str                            # taxonomy 키 중 하나
    iteration_count: int = Field(ge=0)
    last_hint_level: HintLevel
    allowed_hint_level: HintLevel                 # 이번 턴 상한


class DialogueGap(Artifact):
    """Tier 3 핵심. reference_solution / forbidden_content / full_student_answer 는
    *필드로 존재하지 않으며*, extra="forbid" 가 외부 주입도 막는다 (INV-2/3)."""

    req_id: str
    student_status: StudentStatus
    pedagogical_goal: str
    prior_turns_summary: str | None = None


# --- (1b) validator_rules.json  — Validator 만 읽음 ---------------------------

class ValidatorRules(Artifact):
    req_id: str
    forbidden_content: list[str]                  # 정답 숫자·식 문자열 (예: "8명", "15-7")
    forbidden_nl_patterns: list[str] = Field(default_factory=list)  # 정답을 흘리는 한국어 표현
    forbidden_markers: list[str] = Field(default_factory=list)       # 선택: 추가 차단 마커


# --- (2) question_draft  — Dialogue → Review ---------------------------------

class QuestionDraft(Artifact):
    req_id: str
    attempt: int = Field(ge=1)
    text: str
    intended_hint_level: HintLevel


# --- (3) review_report.json  — Review → Dialogue(feedback) -------------------

class AdvisoryVerdict(Artifact):
    source: Literal["Q-Critic"] = "Q-Critic"
    result: Verdict
    reasons: list[str] = Field(default_factory=list)


class DeterministicVerdict(Artifact):
    source: Literal["Validator"] = "Validator"
    result: Verdict
    matched_forbidden: list[str] = Field(default_factory=list)


class ReviewReport(Artifact):
    req_id: str
    attempt: int = Field(ge=1)
    question_draft: str
    advisory_verdict: AdvisoryVerdict
    deterministic_verdict: DeterministicVerdict
    final_verdict: Verdict
    retry_hint: str | None = None        # reject 일 때만 (INV-5), Validator 재통과 산물
    approved_question: str | None = None  # pass 일 때만

    @model_validator(mode="after")
    def _check_and_gate(self) -> "ReviewReport":
        # AND 규칙: 둘 다 pass 여야 final pass
        expected = (
            "pass"
            if self.advisory_verdict.result == "pass"
            and self.deterministic_verdict.result == "pass"
            else "reject"
        )
        if self.final_verdict != expected:
            raise ValueError(
                f"final_verdict={self.final_verdict} 가 AND 게이트 결과 {expected} 와 불일치"
            )
        # INV-5 / 일관성: pass↔approved_question, reject↔retry_hint
        if self.final_verdict == "pass":
            if self.approved_question is None:
                raise ValueError("pass 인데 approved_question 이 없음")
            if self.retry_hint is not None:
                raise ValueError("pass 인데 retry_hint 가 있음")
        else:  # reject
            if self.retry_hint is None:
                raise ValueError("reject 인데 retry_hint 가 없음")
            if self.approved_question is not None:
                raise ValueError("reject 인데 approved_question 이 있음")
        return self


# --- (4) approved_question  — 학생에게 전달 -----------------------------------

class ApprovedQuestion(Artifact):
    req_id: str
    text: str
    hint_level: HintLevel
    retries_used: int = Field(ge=0)


# --- (5) session_state.json  — 턴 간 누적 상태 -------------------------------

class SessionState(Artifact):
    lab_id: str
    session_id: str
    turn: int = Field(ge=1)
    hint_level_history: list[HintLevel] = Field(default_factory=list)
    misconception_history: list[str] = Field(default_factory=list)
    resolved_concepts: list[str] = Field(default_factory=list)
    context_reset_count: int = Field(default=0, ge=0)
    prior_turns_summary: str | None = None
    aha_moment_turn: int | None = None


# --- (6) metrics.json  — 정량 지표 -------------------------------------------

class TokenUsage(Artifact):
    analysis: int = 0
    dialogue: int = 0
    review: int = 0
    logging: int = 0


class Metrics(Artifact):
    session_id: str
    lab_id: str
    total_turns: int = Field(ge=0)
    review_retry_total: int = Field(default=0, ge=0)
    review_retry_avg: float = 0.0
    tier3_leak_count: int = Field(default=0, ge=0)   # §6 절대 기준: 0
    validator_reject_count: int = Field(default=0, ge=0)
    qcritic_reject_count: int = Field(default=0, ge=0)
    context_reset_count: int = Field(default=0, ge=0)
    aha_reached: bool = False
    hint_level_max: HintLevel = 0
    tokens: TokenUsage = Field(default_factory=TokenUsage)
    cost_usd: float = 0.0


# --- (7) event_log.jsonl  — append-only 이벤트 스트림 (closed-loop 척추, INV-6) ---
# Orchestrator 가 모든 루프 상태 전이마다 1 이벤트를 append 한다(덮어쓰기·삭제 없음).
# 정답·forbidden 원문은 data 에 값으로 담지 않는다(결과 enum·카운트·req_id 참조만).
# metrics.json / PATH.md 는 이 로그의 투영(projection)이다 → src/event_log.py:metrics_from_events.

EventType = Literal[
    "turn_started",       # 한 턴 시작
    "packet_created",     # task packet(dialogue_gap) 발행
    "draft_generated",    # worker(Dialogue) 초안 산출
    "gate_evaluated",     # deterministic gate(+advisory) 판정
    "retry_triggered",    # Backpressure 재생성
    "question_approved",  # AND 게이트 통과(또는 안전 폴백) → 학생 전달
    "context_reset",      # 재생성 한도 초과/주기적 리셋
    "judge_aborted",      # Judge 가 정답 베낌 감지해 중단
    "turn_committed",     # 턴 종료 롤업(session_state 영속화 직후) — metrics 투영의 fold 단위
    "session_ended",      # 세션 종료
]


class Event(Artifact):
    """append-only 이벤트 1건. seq=append 순서(=replay 순서), ts=ISO8601(호출측 주입)."""

    seq: int = Field(ge=1)
    req_id: str
    event: EventType
    ts: str = ""                                   # 호출측 주입 (Date.now 비결정성 회피; 기본 빈 문자열)
    data: dict[str, Any] = Field(default_factory=dict)


# Dialogue 가 절대 봐서는 안 되는 키 (테스트가 참조하는 단일 출처)
TIER3_FORBIDDEN_KEYS: frozenset[str] = frozenset(
    {"reference_solution", "correct_answer", "full_student_answer", "forbidden_content"}
)
