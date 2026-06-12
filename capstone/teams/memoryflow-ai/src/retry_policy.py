"""Retry policy for the closed-loop MemoryFlow AI agent."""


class RetryPolicy:
    """Build retry instructions from intent, memory, and judge feedback."""

    def __init__(self, max_retries):
        self.max_retries = max_retries

    def should_retry(self, judge_result, retry_count):
        """Return True when judge failed and retry budget remains."""
        return not judge_result.get("passed", False) and retry_count < self.max_retries

    def build_retry_prompt(self, user_input, judge_result, replayed_memories=None, intent_analysis=None):
        """Build an explicit natural-answer retry prompt."""
        intent_analysis = intent_analysis or {}
        reason_text = ", ".join(judge_result.get("reasons", [])) or "평가 기준 미달"
        memory_text = self._format_memory(replayed_memories or [])
        intent = intent_analysis.get("intent", "unknown")
        target = intent_analysis.get("target", "unknown")

        return (
            "이전 답변은 closed-loop judge를 통과하지 못했다.\n"
            f"- 사용자 의도: {intent} / {target}\n"
            f"- 실패 이유: {reason_text}\n\n"
            "다음 replay memory를 반드시 참고하라.\n"
            f"{memory_text}\n\n"
            "더 자연스럽고 구체적인 문장으로 답변하라. 단순 확인 문장으로 끝내지 마라.\n"
            f"질문: {user_input}"
        )

    def _format_memory(self, replayed_memories):
        """Format replayed memories for retry prompts."""
        if not replayed_memories:
            return "- 사용 가능한 memory가 없습니다."
        return "\n".join(f"- {memory.get('text', str(memory))}" for memory in replayed_memories)
