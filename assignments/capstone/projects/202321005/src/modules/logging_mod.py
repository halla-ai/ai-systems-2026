"""Logging Module — The Observer (Path Tracker).

대화를 관찰만 한다(개입 X). 정답·학생 코드 원문은 보지 않고 메타데이터만 수집한다.
SessionState 갱신, Metrics 집계, prior_turns_summary 압축(Compaction), PATH.md 생성.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..schemas import ApprovedQuestion, DialogueGap, Metrics, SessionState, TokenUsage


@dataclass
class _Accum:
    """세션 누적 카운터 (메타만)."""

    total_turns: int = 0
    review_retry_total: int = 0
    qcritic_reject_count: int = 0
    validator_reject_count: int = 0
    context_reset_count: int = 0
    tier3_leak_count: int = 0
    hint_levels: list[int] = field(default_factory=list)
    aha_reached: bool = False


class LoggingModule:
    def __init__(self, session_id: str, lab_id: str) -> None:
        self._session_id = session_id
        self._lab_id = lab_id
        self._acc = _Accum()

    def log_turn(
        self,
        state: SessionState,
        gap: DialogueGap,
        approved: ApprovedQuestion,
        *,
        retries_used: int,
        qcritic_rejects: int,
        validator_rejects: int,
        context_reset: bool,
        aha: bool,
        tier3_leak: bool = False,
    ) -> SessionState:
        """한 턴 종료 후 상태·지표를 갱신해 새 SessionState 를 반환한다."""
        a = self._acc
        a.total_turns += 1
        a.review_retry_total += retries_used
        a.qcritic_reject_count += qcritic_rejects
        a.validator_reject_count += validator_rejects
        a.context_reset_count += int(context_reset)
        a.tier3_leak_count += int(tier3_leak)
        a.hint_levels.append(approved.hint_level)
        if aha:
            a.aha_reached = True

        misc = gap.student_status.misconception
        new_history = state.misconception_history + [misc]
        # 진전 감지(휴리스틱): 같은 오개념이 끊기면 직전 오개념을 resolved 로
        resolved = list(state.resolved_concepts)
        if len(new_history) >= 2 and new_history[-1] != new_history[-2]:
            prev = new_history[-2]
            if prev not in resolved:
                resolved.append(prev)

        return SessionState(
            lab_id=state.lab_id,
            session_id=state.session_id,
            turn=state.turn,
            hint_level_history=state.hint_level_history + [approved.hint_level],
            misconception_history=new_history,
            resolved_concepts=resolved,
            context_reset_count=a.context_reset_count,
            prior_turns_summary=self._compact(new_history, resolved),
            aha_moment_turn=state.turn if (aha and state.aha_moment_turn is None) else state.aha_moment_turn,
        )

    def _compact(self, misconception_history: list[str], resolved: list[str]) -> str:
        """Compaction (Week 5): 과거 턴을 1문장으로 압축. 정답 단서 미포함."""
        cur = misconception_history[-1] if misconception_history else "unknown"
        resolved_str = ", ".join(resolved) if resolved else "없음"
        return f"이해 완료: {resolved_str}. 현재 잔여 오개념: {cur}."

    def finalize(self, cost_usd: float = 0.0, tokens: TokenUsage | None = None) -> Metrics:
        a = self._acc
        avg = round(a.review_retry_total / a.total_turns, 2) if a.total_turns else 0.0
        return Metrics(
            session_id=self._session_id,
            lab_id=self._lab_id,
            total_turns=a.total_turns,
            review_retry_total=a.review_retry_total,
            review_retry_avg=avg,
            tier3_leak_count=a.tier3_leak_count,
            validator_reject_count=a.validator_reject_count,
            qcritic_reject_count=a.qcritic_reject_count,
            context_reset_count=a.context_reset_count,
            aha_reached=a.aha_reached,
            hint_level_max=max(a.hint_levels) if a.hint_levels else 0,  # type: ignore[arg-type]
            tokens=tokens or TokenUsage(),
            cost_usd=cost_usd,
        )

    def render_path_md(self, state: SessionState, metrics: Metrics) -> str:
        """사람용 학습 경로 리포트 (proposal 부록 A 형식)."""
        aha = f"Turn {state.aha_moment_turn}" if state.aha_moment_turn else "미도달"
        leak_flag = "" if metrics.tier3_leak_count == 0 else "  ⚠️ 누출 발생!"
        resolved = ", ".join(state.resolved_concepts) if state.resolved_concepts else "—"
        return (
            f"# PATH.md — 학습 경로 리포트\n\n"
            f"## 세션\n"
            f"- session_id: {state.session_id}\n"
            f"- lab_id: {state.lab_id}\n"
            f"- 총 턴 수: {metrics.total_turns}\n\n"
            f"## 학습 궤적\n"
            f"- 힌트 수위 변화: {state.hint_level_history}\n"
            f"- 오개념 추이: {state.misconception_history}\n"
            f"- 이해 완료 개념: {resolved}\n"
            f"- Aha-moment: {aha}\n\n"
            f"## 시스템 품질 지표 (3-tier 방어 성능)\n"
            f"- Tier 2 Advisory (Q-Critic) reject: {metrics.qcritic_reject_count}\n"
            f"- Tier 2 Deterministic (Validator) reject: {metrics.validator_reject_count}\n"
            f"- Tier 2 Backpressure 재생성 평균: {metrics.review_retry_avg}회 / 질문\n"
            f"- Tier 3 (Structural) 누출: {metrics.tier3_leak_count}건{leak_flag}\n"
            f"- Context Reset 발동: {metrics.context_reset_count}회\n"
        )
