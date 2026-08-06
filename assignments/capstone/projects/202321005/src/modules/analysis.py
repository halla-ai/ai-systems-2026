"""Analysis Module — The Truth Center (Judge + Planner).

정답에 접근하는 유일한 모듈. 출력은 반드시 두 아티팩트로 분리한다 (INV-2):
  - DialogueGap     (정답 0) → Dialogue·Q-Critic
  - ValidatorRules  (forbidden) → Validator

reference_solution(정답)은 lab dict(메모리)에만 존재하며 어떤 출력에도 쓰지 않는다 (INV-1).
lab dict 는 디스크에 다시 저장하지 않으므로(orchestrator._persist 가 기록하지 않음) 정답이 새지 않는다.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from ..llm import LLMClient
from ..prompts import load_system_prompt
from ..schemas import (
    DialogueGap,
    HintLevel,
    SessionState,
    StudentStatus,
    Submission,
    ValidatorRules,
    make_req_id,
)

LABS_DIR = Path(__file__).resolve().parent.parent.parent / "labs"


class _PlannerOutput(BaseModel):
    """Analysis LLM 의 내부 출력 계약 (아티팩트가 아님)."""

    model_config = ConfigDict(extra="forbid")

    judge_verdict: str = Field(pattern="^(original|copied)$")
    student_mistake: str
    misconception: str
    pedagogical_goal: str
    forbidden_content: list[str] = Field(default_factory=list)
    forbidden_nl_patterns: list[str] = Field(default_factory=list)


@dataclass
class AnalysisResult:
    rejected: bool                       # Judge 가 베낌 감지 → 파이프라인 중단
    gap: DialogueGap | None
    rules: ValidatorRules | None


def load_lab(lab_id: str) -> dict:
    """lab bank(정답 포함)를 메모리로 로드한다. 디스크에 다시 저장하지 않는다(INV-1)."""
    path = LABS_DIR / f"{lab_id.lower().replace('-', '_')}.json"
    return json.loads(path.read_text(encoding="utf-8"))


class AnalysisModule:
    def __init__(self, client: LLMClient) -> None:
        self._client = client
        self._system = load_system_prompt("analysis")

    def _compute_allowed_level(
        self, planner: _PlannerOutput, state: SessionState
    ) -> HintLevel:
        """같은 오개념이 2턴 이상 지속되면 수위 +1 (상한 3)."""
        last = state.hint_level_history[-1] if state.hint_level_history else 0
        history = state.misconception_history
        persists = (
            len(history) >= 1
            and history[-1] == planner.misconception
            and last >= 1
        )
        level = min(3, last + 1) if persists else max(1, last)
        return level  # type: ignore[return-value]

    def process(
        self, submission: Submission, state: SessionState, lab: dict
    ) -> AnalysisResult:
        req_id = make_req_id(submission.lab_id, submission.turn)

        # 정답 영역(lab)을 student_answer 와 함께 LLM 에 제공 (Analysis 만 가능)
        user = json.dumps(
            {
                "reference_solution": lab["reference_solution"],
                "answer_concepts": lab["answer_concepts"],
                "misconception_taxonomy": lab["misconception_taxonomy"],
                "forbidden_templates": lab["forbidden_templates"],
                "student_answer": submission.student_answer,
                "student_message": submission.student_message,
                "iteration_count": submission.turn - 1,
            },
            ensure_ascii=False,
        )
        planner = self._client.structured(
            role="analysis", system=self._system, user=user, schema=_PlannerOutput
        )

        if planner.judge_verdict == "copied":
            return AnalysisResult(rejected=True, gap=None, rules=None)

        last_level = state.hint_level_history[-1] if state.hint_level_history else 0
        allowed = self._compute_allowed_level(planner, state)

        gap = DialogueGap(
            req_id=req_id,
            student_status=StudentStatus(
                student_mistake=planner.student_mistake,
                misconception=planner.misconception,
                iteration_count=submission.turn - 1,
                last_hint_level=last_level,  # type: ignore[arg-type]
                allowed_hint_level=allowed,
            ),
            pedagogical_goal=planner.pedagogical_goal,
            prior_turns_summary=state.prior_turns_summary,
        )
        rules = ValidatorRules(
            req_id=req_id,
            forbidden_content=planner.forbidden_content,
            forbidden_nl_patterns=planner.forbidden_nl_patterns,
        )
        return AnalysisResult(rejected=False, gap=gap, rules=rules)
