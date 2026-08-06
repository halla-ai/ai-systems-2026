"""Review Module — The Quality Filter.

Advisory(Q-Critic, LLM) ∥ Deterministic(Validator, 코드) 두 센서를 결합한 AND 게이트.
둘 다 pass 여야 질문이 전달된다. reject 면 retry_hint 를 합성하되, 그 retry_hint 도
Validator 를 한 번 더 통과해야 한다 (INV-5, 이중 필터).
"""

from __future__ import annotations

import json

from .. import validator
from ..llm import LLMClient
from ..prompts import load_system_prompt
from ..schemas import (
    AdvisoryVerdict,
    DialogueGap,
    QuestionDraft,
    ReviewReport,
    ValidatorRules,
)

# INV-5 위반(retry_hint 가 정답 누출) 시 대체할 안전 문구
_SAFE_RETRY_HINT = "질문을 더 추상적인 개념 수준으로 다시 구성할 것 (구체적 표현·코드 금지)."


class ReviewModule:
    def __init__(self, client: LLMClient) -> None:
        self._client = client
        self._system = load_system_prompt("qcritic")  # SOCRATES.md 상속됨

    def _advisory(self, draft: QuestionDraft, gap: DialogueGap) -> AdvisoryVerdict:
        # Q-Critic 은 forbidden 을 보지 않는다 — gap(정답0)만 전달
        user = json.dumps(
            {
                "question_draft": draft.text,
                "intended_hint_level": draft.intended_hint_level,
                "pedagogical_goal": gap.pedagogical_goal,
                "student_status": gap.student_status.model_dump(),
            },
            ensure_ascii=False,
        )
        return self._client.structured(
            role="qcritic", system=self._system, user=user, schema=AdvisoryVerdict
        )

    def _synthesize_retry_hint(
        self, advisory: AdvisoryVerdict, matched_forbidden: list[str], rules: ValidatorRules
    ) -> str:
        """Advisory 우선 + Deterministic 부속 으로 retry_hint 합성 후 INV-5 재검증."""
        parts: list[str] = list(advisory.reasons)
        if matched_forbidden:
            parts.append("금지 표현이 감지됨: 더 추상적인 어휘로 우회할 것")
        hint = " / ".join(parts) if parts else _SAFE_RETRY_HINT
        # INV-5: retry_hint 자체가 정답을 흘리면 안 됨 → Validator 재통과
        if validator.contains_forbidden(hint, rules):
            return _SAFE_RETRY_HINT
        return hint

    def check(
        self, draft: QuestionDraft, gap: DialogueGap, rules: ValidatorRules
    ) -> ReviewReport:
        # 두 센서는 개념적으로 병렬(독립 판정). 결정성·테스트 용이성을 위해 순차 실행.
        advisory = self._advisory(draft, gap)
        deterministic = validator.evaluate(draft.text, rules)

        is_pass = advisory.result == "pass" and deterministic.result == "pass"
        final = "pass" if is_pass else "reject"

        if is_pass:
            return ReviewReport(
                req_id=draft.req_id,
                attempt=draft.attempt,
                question_draft=draft.text,
                advisory_verdict=advisory,
                deterministic_verdict=deterministic,
                final_verdict=final,
                retry_hint=None,
                approved_question=draft.text,
            )

        retry_hint = self._synthesize_retry_hint(
            advisory, deterministic.matched_forbidden, rules
        )
        return ReviewReport(
            req_id=draft.req_id,
            attempt=draft.attempt,
            question_draft=draft.text,
            advisory_verdict=advisory,
            deterministic_verdict=deterministic,
            final_verdict=final,
            retry_hint=retry_hint,
            approved_question=None,
        )
