"""Strict judge evaluation for MemoryFlow AI."""

import re


class Judge:
    """Evaluate relevance, memory usage, specificity, and naturalness."""

    TEMPLATE_PHRASES = [
        "입력 내용을 확인했습니다",
        "질문을 확인했습니다",
        "아직 관련 memory는 없지만",
    ]

    def evaluate(self, user_input, response, replayed_memories=None, intent_analysis=None, use_memory=True):
        """Return pass/fail, score, and reasons."""
        replayed_memories = replayed_memories or []
        intent_analysis = intent_analysis or {}
        reasons = []
        score = 0

        if self._is_relevant(user_input, response, intent_analysis):
            score += 1
        else:
            reasons.append("질문과 답변의 관련성이 부족합니다.")

        if 12 <= len(str(response).strip()) <= 1000:
            score += 1
        else:
            reasons.append("응답 길이가 너무 짧거나 깁니다.")

        if use_memory:
            memory_result = self._memory_usage_result(response, replayed_memories, intent_analysis)
        else:
            memory_result = {"passed": True, "reasons": [], "skipped": True}
        if memory_result["passed"]:
            score += 2
        else:
            reasons.extend(memory_result["reasons"])

        naturalness = self._naturalness_result(response, replayed_memories)
        if naturalness["passed"]:
            score += 1
        else:
            reasons.extend(naturalness["reasons"])

        return {
            "passed": score >= 4 and not reasons,
            "score": score,
            "reasons": reasons,
            "memory_evaluation_skipped": not use_memory,
        }

    def _memory_usage_result(self, response, replayed_memories, intent_analysis):
        """Require relevant replayed fact values in the response."""
        if not replayed_memories:
            return {"passed": True, "reasons": []}

        intent = intent_analysis.get("intent", "")
        required = []
        for memory in replayed_memories:
            if memory.get("type") == "fact":
                if intent in {"ask_name", "ask_project", "ask_capstone", "ask_preference", "ask_summary"}:
                    required.append(memory)
            elif memory.get("type") == "summary" and intent == "ask_summary":
                required.append(memory)

        if not required:
            return {"passed": True, "reasons": []}

        response_text = str(response)
        missing = []
        for memory in required:
            value = str(memory.get("value") or memory.get("text") or "")
            if value and value not in response_text:
                missing.append(value)

        if missing:
            return {"passed": False, "reasons": ["memory 활용 실패"]}
        return {"passed": True, "reasons": []}

    def _naturalness_result(self, response, replayed_memories):
        """Penalize template-like answers when memory was available."""
        response_text = str(response)
        if replayed_memories and any(phrase in response_text for phrase in self.TEMPLATE_PHRASES):
            return {"passed": False, "reasons": ["템플릿형 응답으로 memory 기반 답변처럼 보이지 않습니다."]}
        if len(response_text.split()) <= 2 and replayed_memories:
            return {"passed": False, "reasons": ["응답이 지나치게 짧아 구체성이 부족합니다."]}
        return {"passed": True, "reasons": []}

    def _is_relevant(self, user_input, response, intent_analysis):
        """Check intent-aware relevance."""
        intent = intent_analysis.get("intent", "")
        response_text = str(response)

        checks = {
            "ask_name": ["이름", "님", "기억"],
            "ask_project": ["프로젝트", "만들", "진행", "Unity", "게임"],
            "ask_capstone": ["캡스톤", "주제", "MemoryFlow"],
            "ask_preference": ["선호", "좋아", "관심"],
            "ask_summary": ["기억", "요약", "최근", "프로젝트", "캡스톤"],
            "remember_fact": ["기억", "저장", "memory"],
        }
        if intent in checks:
            return any(term in response_text for term in checks[intent])

        user_keywords = set(re.findall(r"[A-Za-z0-9_]+|[가-힣]+", str(user_input).lower()))
        response_keywords = set(re.findall(r"[A-Za-z0-9_]+|[가-힣]+", response_text.lower()))
        return bool(user_keywords.intersection(response_keywords))
