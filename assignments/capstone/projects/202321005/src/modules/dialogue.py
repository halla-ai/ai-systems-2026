"""Dialogue Module — The Frontstage (Tutor).

학생과 대화하는 유일한 모듈. DialogueGap 만 입력으로 받는다.
정답·forbidden 은 입력 스키마에 존재하지 않으므로 물리적으로 볼 수 없다 (Tier 3).
"""

from __future__ import annotations

import json

from pydantic import BaseModel, ConfigDict

from ..llm import LLMClient
from ..prompts import load_system_prompt
from ..schemas import DialogueGap, HintLevel, QuestionDraft


class _TutorOutput(BaseModel):
    """Dialogue LLM 의 내부 출력 계약 (아티팩트가 아님)."""

    model_config = ConfigDict(extra="forbid")

    text: str
    intended_hint_level: HintLevel


class DialogueModule:
    def __init__(self, client: LLMClient) -> None:
        self._client = client
        self._system = load_system_prompt("dialogue")  # SOCRATES.md 상속됨

    def generate(
        self, gap: DialogueGap, attempt: int, feedback: str | None = None
    ) -> QuestionDraft:
        # gap 에는 정답/forbidden 이 없다 — 입력 자체가 Tier 3 보장
        payload: dict = {"dialogue_gap": gap.model_dump()}
        if feedback:
            payload["retry_hint"] = feedback
        user = json.dumps(payload, ensure_ascii=False)

        out = self._client.structured(
            role="dialogue", system=self._system, user=user, schema=_TutorOutput
        )
        return QuestionDraft(
            req_id=gap.req_id,
            attempt=attempt,
            text=out.text,
            intended_hint_level=out.intended_hint_level,
        )
