"""공유 픽스처. FakeClient 기반 결정적 시나리오."""

from __future__ import annotations

import pytest

from src.llm import FakeClient


def default_handler(role: str, user: str, schema):
    """1차 Dialogue 초안이 정답("8명")을 흘려 Validator reject → 재생성 → 통과."""
    if role == "analysis":
        return {
            "judge_verdict": "original",
            "student_mistake": "줄어드는 상황인데 덧셈을 함",
            "misconception": "operation_confusion",
            "pedagogical_goal": "학생이 '내리는 것 = 줄어드는 것'을 깨닫게 한다",
            "forbidden_content": ["8명", "15-7", "15 - 7"],
            "forbidden_nl_patterns": ["정답은 팔", "8명이 남"],
        }
    if role == "dialogue":
        if "retry_hint" in user:
            return {"text": "사람이 내리면 버스 안 사람 수는 어떻게 될까요?", "intended_hint_level": 1}
        return {"text": "15에서 7을 빼면 8명이 남겠죠?", "intended_hint_level": 2}
    if role == "qcritic":
        return {"source": "Q-Critic", "result": "pass", "reasons": []}
    raise ValueError(role)


@pytest.fixture
def fake_client() -> FakeClient:
    return FakeClient(default_handler)
