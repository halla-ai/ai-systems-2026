"""Self-reflection memory management for MemoryFlow AI."""

from datetime import datetime


class ReflectionManager:
    """Create reflection memories from judge outcomes."""

    def __init__(self, memory_store):
        self.memory_store = memory_store

    def reflect(self, user_input, intent, judge_result, replayed_memories):
        """Create a reflection memory after each judged turn."""
        if judge_result.get("passed"):
            text = self._success_reflection(intent, replayed_memories)
        else:
            text = self._failure_reflection(intent, judge_result)

        if not text:
            return None

        memory = {
            "type": "reflection",
            "key": "self_reflection",
            "value": text,
            "text": text,
            "importance": 7,
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "updated_at": datetime.now().isoformat(timespec="seconds"),
            "last_accessed": None,
            "access_count": 0,
            "status": "active",
            "history": [],
            "conflict_count": 0,
            "source": user_input,
        }
        self.memory_store.add_memory(memory)
        return memory

    def _failure_reflection(self, intent, judge_result):
        """Build reflection text for judge failure."""
        reasons = ", ".join(judge_result.get("reasons", []))
        if intent.get("intent") == "ask_name":
            return "이름 질문에서는 name memory를 반드시 활용해야 한다."
        if intent.get("intent") in {"ask_project", "ask_summary"}:
            return "프로젝트 질문에서는 project memory와 summary memory를 함께 활용해야 한다."
        return f"Judge 실패 이유를 다음 응답에 반영해야 한다: {reasons}"

    def _success_reflection(self, intent, replayed_memories):
        """Optionally store a useful success learning point."""
        memory_types = {memory.get("type") for memory in replayed_memories}
        if intent.get("intent") in {"ask_project", "ask_summary"} and {"fact", "summary"}.issubset(memory_types):
            return "project memory와 summary memory를 함께 사용하면 응답 품질이 높아진다."
        return None
