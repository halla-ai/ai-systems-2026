"""Event Log — closed-loop 의 append-only 이벤트 스트림 (docs/artifacts.md §2 (7), INV-6).

Orchestrator 가 모든 루프 상태 전이마다 1 이벤트를 **추가만** 한다(덮어쓰기·삭제 없음).
정답·forbidden 원문은 값으로 담지 않는다(결과 enum·카운트·req_id 참조만) → Tier 3 유지.

이 로그가 단일 진실 원천(SSOT)이며, metrics.json / PATH.md / replay snapshot 은 모두
여기서 파생된다. `metrics_from_events` 가 그 투영(projection)이며,
LoggingModule.finalize() 와 동일한 수치를 내야 한다 (test_event_log 가 검증).
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Iterable

from .schemas import Event, Metrics, TokenUsage


class EventLog:
    """append-only 이벤트 writer. 한 run = 한 파일(`event_log.jsonl`, JSON Lines)."""

    def __init__(
        self,
        path: str | Path | None = None,
        clock: Callable[[], str] | None = None,
    ) -> None:
        self._path = Path(path) if path is not None else None
        # 기본 clock 은 빈 ts (결정적 테스트). 운영에서는 ISO8601 clock 을 주입한다.
        self._clock = clock or (lambda: "")
        self._seq = 0
        self.events: list[Event] = []
        if self._path is not None:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._path.write_text("", encoding="utf-8")  # 새 run 시작 = 빈 파일

    def emit(self, event: str, req_id: str, **data) -> Event:
        """이벤트 1건을 append 한다. seq 는 1부터 단조 증가(=replay 순서)."""
        self._seq += 1
        ev = Event(seq=self._seq, req_id=req_id, event=event, ts=self._clock(), data=data)
        self.events.append(ev)
        if self._path is not None:
            with self._path.open("a", encoding="utf-8") as f:
                f.write(ev.model_dump_json() + "\n")
        return ev

    @staticmethod
    def load(path: str | Path) -> list[Event]:
        """`event_log.jsonl` 을 seq 순(=기록 순) Event 리스트로 읽는다 (replay 입력)."""
        lines = Path(path).read_text(encoding="utf-8").splitlines()
        return [Event.model_validate_json(ln) for ln in lines if ln.strip()]


def metrics_from_events(
    events: Iterable[Event],
    *,
    session_id: str,
    lab_id: str,
    cost_usd: float = 0.0,
    tokens: TokenUsage | None = None,
) -> Metrics:
    """event_log 를 fold 해 Metrics 를 재구성한다 (replay/projection, INV-6).

    `turn_committed` 이벤트(턴별 롤업)를 합산한다 — LoggingModule.log_turn 이 받는 값과
    동일 단위라 finalize() 와 같은 수치가 나온다. 세부 `gate_evaluated` 는 사람용 실패경로
    서사이며, 합산식에는 turn_committed 만 쓴다(이중 계수 방지).
    """
    total_turns = 0
    review_retry_total = 0
    qcritic_reject_count = 0
    validator_reject_count = 0
    context_reset_count = 0
    tier3_leak_count = 0
    hint_levels: list[int] = []
    aha_reached = False

    for ev in events:
        if ev.event != "turn_committed":
            continue
        d = ev.data
        total_turns += 1
        review_retry_total += int(d.get("retries_used", 0))
        qcritic_reject_count += int(d.get("qcritic_rejects", 0))
        validator_reject_count += int(d.get("validator_rejects", 0))
        context_reset_count += int(bool(d.get("context_reset", False)))
        tier3_leak_count += int(bool(d.get("tier3_leak", False)))
        hint_levels.append(int(d.get("hint_level", 0)))
        if d.get("aha"):
            aha_reached = True

    avg = round(review_retry_total / total_turns, 2) if total_turns else 0.0
    return Metrics(
        session_id=session_id,
        lab_id=lab_id,
        total_turns=total_turns,
        review_retry_total=review_retry_total,
        review_retry_avg=avg,
        tier3_leak_count=tier3_leak_count,
        validator_reject_count=validator_reject_count,
        qcritic_reject_count=qcritic_reject_count,
        context_reset_count=context_reset_count,
        aha_reached=aha_reached,
        hint_level_max=max(hint_levels) if hint_levels else 0,  # type: ignore[arg-type]
        tokens=tokens or TokenUsage(),
        cost_usd=cost_usd,
    )
