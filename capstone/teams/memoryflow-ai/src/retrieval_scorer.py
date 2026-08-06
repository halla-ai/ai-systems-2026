"""Retrieval scoring layer for MemoryFlow AI."""

from datetime import datetime


class RetrievalScorer:
    """Score memories before replay using intent, key, importance, and usage."""

    INTENT_KEY_MAP = {
        "ask_name": {"name"},
        "ask_project": {"project", "capstone_topic", "conversation_summary"},
        "ask_capstone": {"capstone_topic", "conversation_summary"},
        "ask_preference": {"preference"},
        "ask_summary": {"project", "capstone_topic", "name", "conversation_summary"},
    }

    def score_memory(self, memory, intent, keywords):
        """Return a score and human-readable reason for one memory."""
        target_keys = self.INTENT_KEY_MAP.get(intent.get("intent", ""), set())
        target = intent.get("target")
        key = memory.get("key", "")
        text = f"{memory.get('key', '')} {memory.get('value', '')} {memory.get('text', '')}".lower()
        keywords = [keyword.lower() for keyword in keywords or []]

        score = 0.0
        reasons = []

        if key in target_keys:
            score += 0.60
            reasons.append("exact intent match")
        elif target and key == target:
            score += 0.45
            reasons.append("target key match")

        keyword_hits = [keyword for keyword in keywords if keyword and keyword in text]
        if keyword_hits:
            score += min(0.22, 0.07 * len(keyword_hits))
            reasons.append("keyword match")

        importance = int(memory.get("importance", 1))
        score += min(0.22, importance / 45)
        if importance >= 8:
            reasons.append("high importance")

        access_count = int(memory.get("access_count", 0))
        if access_count:
            score += min(0.10, access_count * 0.02)
            reasons.append("frequently accessed")

        if memory.get("status") == "protected":
            score += 0.15
            reasons.append("protected memory")

        if self._recently_accessed(memory):
            score += 0.05
            reasons.append("recently used")

        return {
            "score": round(min(score, 0.99), 2),
            "reason": " + ".join(reasons) if reasons else "low relevance",
        }

    def _recently_accessed(self, memory):
        """Return True when last_accessed is present and parseable."""
        value = memory.get("last_accessed")
        if not value:
            return False
        try:
            datetime.fromisoformat(value)
        except ValueError:
            return False
        return True
