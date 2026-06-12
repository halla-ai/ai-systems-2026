"""Token estimation utilities for MemoryFlow AI.

This module intentionally avoids external tokenizers. The estimate is simple
but deterministic: Korean, English, and number chunks are counted as token-like
units, while punctuation is ignored.
"""

import re


class TokenMonitor:
    """Estimate token usage for individual text and conversation messages."""

    _TOKEN_PATTERN = re.compile(r"[A-Za-z0-9_]+|[가-힣]+|[^\sA-Za-z0-9_가-힣]")

    def count_tokens(self, text):
        """Return an approximate token count for a text string."""
        if not text:
            return 0

        tokens = self._TOKEN_PATTERN.findall(str(text))
        meaningful_tokens = [token for token in tokens if token.strip()]
        return len(meaningful_tokens)

    def estimate_conversation_tokens(self, messages):
        """Return the approximate token count for a list of chat messages."""
        total = 0
        for message in messages:
            role = str(message.get("role", ""))
            content = str(message.get("content", ""))
            total += self.count_tokens(role)
            total += self.count_tokens(content)
        return total
