"""L4 Event Store — append-only .events.jsonl with replay snapshot."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class ToolEvent:
    tool: str
    action: str
    status: str
    input_summary: str = ""
    output_summary: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class AgentEvent:
    event_id: str
    run_id: str
    timestamp: str
    event_type: str
    agent_role: str
    agent_name: str = ""
    phase: str = ""
    payload: dict[str, Any] = field(default_factory=dict)
    tool_event: ToolEvent | None = None

    def to_dict(self) -> dict[str, Any]:
        data = {
            "event_id": self.event_id,
            "run_id": self.run_id,
            "timestamp": self.timestamp,
            "event_type": self.event_type,
            "agent_role": self.agent_role,
            "agent_name": self.agent_name,
            "phase": self.phase,
            "payload": self.payload,
        }
        if self.tool_event:
            data["tool_event"] = self.tool_event.to_dict()
        return data


class EventStore:
    """Append-only JSONL event log with replay snapshot support."""

    def __init__(self, output_dir: Path, run_id: str | None = None) -> None:
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.run_id = run_id or str(uuid4())
        self.events_path = self.output_dir / ".events.jsonl"
        self.snapshot_path = self.output_dir / ".events.snapshot.json"
        self._events: list[AgentEvent] = []

    def append(
        self,
        event_type: str,
        agent_role: str,
        *,
        agent_name: str = "",
        phase: str = "",
        payload: dict[str, Any] | None = None,
        tool_event: ToolEvent | None = None,
    ) -> AgentEvent:
        event = AgentEvent(
            event_id=str(uuid4()),
            run_id=self.run_id,
            timestamp=_utc_now(),
            event_type=event_type,
            agent_role=agent_role,
            agent_name=agent_name,
            phase=phase,
            payload=payload or {},
            tool_event=tool_event,
        )
        self._events.append(event)
        with self.events_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(event.to_dict(), ensure_ascii=False) + "\n")
        return event

    def save_snapshot(self, state: dict[str, Any]) -> None:
        snapshot = {
            "run_id": self.run_id,
            "timestamp": _utc_now(),
            "event_count": len(self._events),
            "last_event_id": self._events[-1].event_id if self._events else None,
            "state": state,
        }
        self.snapshot_path.write_text(
            json.dumps(snapshot, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def replay(self) -> list[dict[str, Any]]:
        if not self.events_path.exists():
            return [e.to_dict() for e in self._events]
        events = []
        for line in self.events_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                events.append(json.loads(line))
        return events

    @classmethod
    def load_snapshot(cls, snapshot_path: Path) -> dict[str, Any]:
        return json.loads(snapshot_path.read_text(encoding="utf-8"))
