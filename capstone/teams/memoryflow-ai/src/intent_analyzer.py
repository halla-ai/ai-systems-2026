"""Intent analysis for MemoryFlow AI.

The analyzer is rule-based, but it gives the rest of the system a clear
semantic signal so the agent behaves less like a fixed template responder.
"""

import re


class IntentAnalyzer:
    """Classify user input into high-level intent, target, and keywords."""

    def analyze(self, user_input):
        """Return intent metadata for one user input."""
        text = self._normalize(user_input)
        lower = text.lower()
        keywords = self._keywords(text)

        if lower in {"exit", "quit"}:
            return self._result("exit", "session", keywords)
        if lower == "stats":
            return self._result("command_stats", "memory", keywords)
        if lower == "show memory":
            return self._result("command_show_memory", "memory", keywords)
        if lower == "demo":
            return self._result("command_demo", "demo", keywords)

        if self._looks_like_fact(text):
            return self._result("remember_fact", self._fact_target(text), keywords)
        if self._is_name_question(text):
            return self._result("ask_name", "name", keywords)
        if self._is_project_question(text):
            return self._result("ask_project", "project", keywords)
        if self._is_capstone_question(text):
            return self._result("ask_capstone", "capstone_topic", keywords)
        if self._is_preference_question(text):
            return self._result("ask_preference", "preference", keywords)
        if self._is_summary_question(text):
            return self._result("ask_summary", "project", keywords)
        return self._result("general_chat", "general", keywords)

    def _result(self, intent, target, keywords):
        """Build a stable intent-analysis result."""
        return {
            "intent": intent,
            "target": target,
            "keywords": keywords,
        }

    def _is_name_question(self, text):
        return any(pattern in text for pattern in ["내가 누구", "나 누구", "이름이 뭐", "내 이름이 뭐"])

    def _is_project_question(self, text):
        if any(pattern in text for pattern in ["뭘 만들", "무엇을 만들", "뭐 만들", "하고 있었"]):
            return True
        return "프로젝트" in text and any(term in text for term in ["뭐", "무엇", "뭐였", "알려"])

    def _is_capstone_question(self, text):
        return "캡스톤" in text and any(term in text for term in ["뭐", "무엇", "알려", "?"])

    def _is_preference_question(self, text):
        return any(pattern in text for pattern in ["좋아하는", "선호", "관심"])

    def _is_summary_question(self, text):
        patterns = ["최근에 무슨 얘기", "요즘 뭐", "작업 흐름", "뭐 하고 있었", "무슨 이야기"]
        return any(pattern in text for pattern in patterns)

    def _looks_like_fact(self, text):
        fact_terms = ["내 이름은", "나는", "내 캡스톤 주제는", "캡스톤 주제는", "내 프로젝트는", "내 직업", "좋아해", "관심"]
        return any(term in text for term in fact_terms)

    def _fact_target(self, text):
        if "이름" in text:
            return "name"
        if "캡스톤" in text:
            return "capstone_topic"
        if "프로젝트" in text or "만들고 있어" in text:
            return "project"
        if "직업" in text or "일하고 있어" in text:
            return "occupation"
        if "좋아해" in text or "관심" in text:
            return "preference"
        return "fact"

    def _keywords(self, text):
        """Extract simple Korean/English/number keywords."""
        tokens = re.findall(r"[A-Za-z0-9_]+|[가-힣]+", text)
        stopwords = {"내", "나는", "나", "뭐야", "뭐", "무엇", "이야", "야", "은", "는", "이", "가", "을", "를"}
        return [token for token in tokens if token not in stopwords and len(token) > 1]

    def _normalize(self, user_input):
        text = str(user_input).strip()
        text = re.sub(r"\s+", " ", text)
        return text
