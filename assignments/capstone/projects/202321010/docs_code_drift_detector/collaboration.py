"""L3 Plan-Work-Review Collaboration — Lead, Planner, Worker, Reviewer state machine."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any
from uuid import uuid4


class CollaborationRole(str, Enum):
    LEAD = "lead"
    PLANNER = "planner"
    WORKER = "worker"
    REVIEWER = "reviewer"


class CollaborationState(str, Enum):
    PLANNED = "planned"
    IN_PROGRESS = "in_progress"
    WORKER_DONE = "worker_done"
    UNDER_REVIEW = "under_review"
    APPROVED = "approved"
    ESCALATED = "escalated"
    HUMAN_REVIEW = "human_review"


# Valid state transitions
TRANSITIONS: dict[CollaborationState, list[CollaborationState]] = {
    CollaborationState.PLANNED: [CollaborationState.IN_PROGRESS],
    CollaborationState.IN_PROGRESS: [CollaborationState.WORKER_DONE],
    CollaborationState.WORKER_DONE: [CollaborationState.UNDER_REVIEW],
    CollaborationState.UNDER_REVIEW: [
        CollaborationState.APPROVED,
        CollaborationState.ESCALATED,
        CollaborationState.HUMAN_REVIEW,
    ],
    CollaborationState.ESCALATED: [CollaborationState.HUMAN_REVIEW],
    CollaborationState.HUMAN_REVIEW: [CollaborationState.APPROVED],
    CollaborationState.APPROVED: [],
}


# Week 7 multi-agent SDLC mapping
AGENT_ROLE_MAP: dict[str, CollaborationRole] = {
    "lead": CollaborationRole.LEAD,
    "planner": CollaborationRole.PLANNER,
    "doc_analyzer": CollaborationRole.WORKER,
    "code_analyzer": CollaborationRole.WORKER,
    "drift_detector": CollaborationRole.WORKER,
    "fix_generator": CollaborationRole.WORKER,
    "qa_agent": CollaborationRole.WORKER,
    "pr_agent": CollaborationRole.WORKER,
    "reviewer": CollaborationRole.REVIEWER,
}


@dataclass
class CollaborationTrace:
    task_id: str
    agent_name: str
    role: CollaborationRole
    state_from: CollaborationState
    state_to: CollaborationState
    note: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "agent_name": self.agent_name,
            "role": self.role.value,
            "state_from": self.state_from.value,
            "state_to": self.state_to.value,
            "note": self.note,
        }


@dataclass
class CollaborationSession:
    run_id: str
    current_state: CollaborationState = CollaborationState.PLANNED
    traces: list[CollaborationTrace] = field(default_factory=list)

    def transition(
        self,
        task_id: str,
        agent_name: str,
        to_state: CollaborationState,
        note: str = "",
    ) -> CollaborationTrace:
        role = AGENT_ROLE_MAP.get(agent_name, CollaborationRole.WORKER)
        allowed = TRANSITIONS.get(self.current_state, [])
        if to_state not in allowed and self.current_state != to_state:
            raise ValueError(
                f"Invalid transition {self.current_state.value} -> {to_state.value}"
            )
        trace = CollaborationTrace(
            task_id=task_id,
            agent_name=agent_name,
            role=role,
            state_from=self.current_state,
            state_to=to_state,
            note=note,
        )
        self.traces.append(trace)
        self.current_state = to_state
        return trace

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "current_state": self.current_state.value,
            "traces": [t.to_dict() for t in self.traces],
        }


def new_task_id() -> str:
    return str(uuid4())
