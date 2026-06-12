"""Smart Memory Replay with retrieval scoring for MemoryFlow AI."""

from memory_store import MemoryStore
from retrieval_scorer import RetrievalScorer


class ReplayEngine:
    """Score all candidate memories and replay the top N."""

    def __init__(self, memory_store=None, max_results=4, retrieval_scorer=None):
        self.memory_store = memory_store or MemoryStore()
        self.max_results = max_results
        self.retrieval_scorer = retrieval_scorer or RetrievalScorer()
        self.last_scores = []

    def replay(self, user_input, intent_analysis=None):
        """Return top scored memory objects for the current input."""
        intent_analysis = intent_analysis or {}
        keywords = intent_analysis.get("keywords", [])
        scored = []

        for memory in self.memory_store.candidate_memories():
            result = self.retrieval_scorer.score_memory(memory, intent_analysis, keywords)
            if result["score"] > 0:
                scored.append(
                    {
                        "memory": memory,
                        "score": result["score"],
                        "reason": result["reason"],
                    }
                )

        scored.sort(key=lambda item: item["score"], reverse=True)
        self.last_scores = scored[: self.max_results]
        self.memory_store.record_retrieval_scores(self.last_scores)
        replayed = [item["memory"] for item in self.last_scores]
        self.memory_store.record_replay_access(replayed)
        return replayed

    def format_replay_block(self, replayed_memories):
        """Format replayed memories for console output."""
        if not replayed_memories:
            return ""
        lines = ["[MEMORY REPLAY]"]
        lines.extend(f"- {self._display_text(memory)}" for memory in replayed_memories)
        return "\n".join(lines)

    def format_retrieval_scores(self):
        """Format retrieval scores for console output."""
        if not self.last_scores:
            return ""

        lines = ["[RETRIEVAL SCORE]"]
        for item in self.last_scores:
            memory = item["memory"]
            label = self._score_label(memory)
            lines.append("")
            lines.append(label)
            lines.append(f"score={item['score']}")
            lines.append(f"reason={item['reason']}")
        return "\n".join(lines)

    def _display_text(self, memory):
        if memory.get("type") in {"fact", "summary", "reflection"}:
            return memory.get("text", "")
        return memory.get("text") or f"이전 대화: {memory.get('user_input', '')}"

    def _score_label(self, memory):
        key = memory.get("key") or memory.get("type", "memory")
        value = memory.get("value") or memory.get("text", "")
        if len(str(value)) > 60:
            value = str(value)[:60] + "..."
        return f"{key}={value}"
