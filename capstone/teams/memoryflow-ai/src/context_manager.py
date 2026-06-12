"""Context compression for long conversations.

Compression keeps the recent conversation compact while preserving important
fact memories such as name, project, and capstone topic outside the summary.
"""

import json
import os

from config import COMPRESSED_CONTEXT_FILE, TOKEN_LIMIT
from token_monitor import TokenMonitor


class ContextManager:
    """Compress previous conversation turns into persisted JSON context."""

    def __init__(self, token_limit=TOKEN_LIMIT, output_file=COMPRESSED_CONTEXT_FILE, memory_store=None):
        self.token_limit = token_limit
        self.output_file = output_file
        self.memory_store = memory_store
        self.token_monitor = TokenMonitor()

    def compress_context(self, messages):
        """Compress older messages when estimated tokens exceed the limit."""
        token_count = self.token_monitor.estimate_conversation_tokens(messages)
        protected_memories = self._protected_memories()
        previous = self._load_compressed_context()
        compression_count = int(previous.get("compression_count", 0))

        if token_count <= self.token_limit:
            compressed = {
                "compressed": False,
                "compression_count": compression_count,
                "token_count": token_count,
                "summary": "",
                "recent_messages": messages,
                "protected_memories": protected_memories,
            }
            self._save_compressed_context(compressed)
            return compressed

        older_messages = messages[:-4] if len(messages) > 4 else messages[:-1]
        recent_messages = messages[-4:] if len(messages) > 4 else messages[-1:]
        summary = self._summarize_messages(older_messages)

        compressed = {
            "compressed": True,
            "compression_count": compression_count + 1,
            "token_count": token_count,
            "summary": summary,
            "recent_messages": recent_messages,
            "protected_memories": protected_memories,
        }
        self._save_compressed_context(compressed)
        return compressed

    def get_statistics(self):
        """Return compressed context count and current compressed token count."""
        data = self._load_compressed_context()
        return {
            "compressed_context_count": int(data.get("compression_count", 0)),
            "token_count": int(data.get("token_count", 0)),
        }

    def _protected_memories(self):
        """Keep high-importance fact memories outside lossy compression."""
        if not self.memory_store:
            return []
        return self.memory_store.get_important_memories(min_importance=8)

    def _summarize_messages(self, messages):
        """Build a compact rule-based summary from previous messages."""
        if not messages:
            return "요약할 이전 대화가 없습니다."

        summary_items = []
        for message in messages:
            role = message.get("role", "unknown")
            content = str(message.get("content", "")).strip()
            if not content:
                continue

            short_content = content[:80]
            if len(content) > 80:
                short_content += "..."
            summary_items.append(f"{role}: {short_content}")

        return " / ".join(summary_items) if summary_items else "이전 대화에 유효한 내용이 없습니다."

    def _load_compressed_context(self):
        """Load current compressed context state."""
        if not os.path.exists(self.output_file):
            return {}
        try:
            with open(self.output_file, "r", encoding="utf-8") as file:
                data = json.load(file)
        except json.JSONDecodeError:
            return {}
        return data if isinstance(data, dict) else {}

    def _save_compressed_context(self, compressed_context):
        """Persist compressed context as UTF-8 JSON."""
        directory = os.path.dirname(self.output_file)
        if directory:
            os.makedirs(directory, exist_ok=True)

        with open(self.output_file, "w", encoding="utf-8") as file:
            json.dump(compressed_context, file, ensure_ascii=False, indent=2)
