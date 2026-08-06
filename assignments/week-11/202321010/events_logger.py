"""
Agent OS Runtime 형식 이벤트 로거
각 이벤트는 JSONL 한 줄씩 저장됨
"""

import json
import uuid
from datetime import datetime, timezone


class EventsLogger:
    """Agent OS Runtime 표준 .events.jsonl 로거"""

    def __init__(self, run_id: str):
        self.run_id = run_id
        self.filepath = f"{run_id}.events.jsonl"
        self._file = open(self.filepath, "w", encoding="utf-8")

    def log_event(self, event_type: str, data: dict) -> dict:
        event = {
            "event_id": str(uuid.uuid4()),
            "event_type": event_type,
            "run_id": self.run_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        event.update(data)
        self._file.write(json.dumps(event, ensure_ascii=False) + "\n")
        self._file.flush()
        return event

    def close(self):
        self._file.close()
