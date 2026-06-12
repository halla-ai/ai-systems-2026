"""Memory usage gate for MemoryFlow AI."""

import re


class MemoryGate:
    """Decide whether a turn should use long-term memory retrieval."""

    MEMORY_INTENTS = {
        "ask_name",
        "ask_project",
        "ask_capstone",
        "ask_preference",
        "ask_summary",
        "remember_fact",
    }

    NO_MEMORY_INTENTS = {
        "technical_question",
        "coding_question",
        "git_command",
        "shell_command",
        "programming_question",
        "general_chat",
    }

    GIT_COMMAND_RE = re.compile(r"^\s*git\s+\S+", re.IGNORECASE)
    PYTHON_COMMAND_RE = re.compile(r"^\s*python(?:3)?\s+-m\s+\S+", re.IGNORECASE)
    SHELL_COMMAND_RE = re.compile(
        r"^\s*(?:cd|dir|ls|pwd|echo|cat|type|npm|pip|pytest|uv|cargo|go|node|pnpm|yarn)\b",
        re.IGNORECASE,
    )
    TECHNICAL_TERMS_RE = re.compile(
        r"\b(?:Unity|Rigidbody2D|Python|JavaScript|TypeScript|React|API|SQL|Docker|Kubernetes|Git)\b",
        re.IGNORECASE,
    )

    def should_use_memory(self, intent, user_input):
        """Return True only when the turn needs memory retrieval."""
        intent_name = intent.get("intent", intent) if isinstance(intent, dict) else str(intent)
        text = str(user_input or "").strip()

        if intent_name in self.NO_MEMORY_INTENTS:
            return False
        if self._looks_like_command_or_technical_question(text):
            return False
        return intent_name in self.MEMORY_INTENTS

    def _looks_like_command_or_technical_question(self, text):
        if self.GIT_COMMAND_RE.search(text):
            return True
        if self.PYTHON_COMMAND_RE.search(text):
            return True
        if self.SHELL_COMMAND_RE.search(text):
            return True
        if self.TECHNICAL_TERMS_RE.search(text) and self._is_question(text):
            return True
        return False

    def _is_question(self, text):
        question_terms = ["?", "뭐야", "무엇", "란", "란?", "설명", "어떻게", "why", "what", "how"]
        lower = text.lower()
        return any(term in lower for term in question_terms)
