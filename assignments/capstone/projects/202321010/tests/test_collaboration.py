"""Tests for L3 collaboration state machine."""

import pytest

from docs_code_drift_detector.collaboration import (
    CollaborationSession,
    CollaborationState,
)


def test_collaboration_state_transitions():
    session = CollaborationSession(run_id="r1")
    session.transition("t1", "lead", CollaborationState.IN_PROGRESS)
    session.transition("t2", "doc_analyzer", CollaborationState.WORKER_DONE)
    session.transition("t3", "drift_detector", CollaborationState.UNDER_REVIEW)
    session.transition("t4", "reviewer", CollaborationState.APPROVED)
    assert session.current_state == CollaborationState.APPROVED
    assert len(session.traces) == 4


def test_invalid_transition_raises():
    session = CollaborationSession(run_id="r2")
    with pytest.raises(ValueError):
        session.transition("t1", "lead", CollaborationState.APPROVED)
