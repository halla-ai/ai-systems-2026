"""
Mock Claude API Client

실제 Anthropic Claude API 키가 없을 때 사용하는 목(mock) 클라이언트.
실제 사용 시 아래 MockClaudeClient 대신 anthropic.Anthropic()으로 교체하면 됩니다.

  실제 사용 예시:
    import anthropic
    claude = anthropic.Anthropic(api_key="sk-ant-...")

  목(mock) 사용 예시 (현재):
    from mock_claude import MockClaudeClient
    claude = MockClaudeClient()
"""

import json
import textwrap


class _MockMessage:
    """anthropic SDK의 응답 객체를 흉내 냅니다."""

    def __init__(self, text: str):
        self.content = [_MockContent(text)]


class _MockContent:
    def __init__(self, text: str):
        self.text = text


class MockClaudeClient:
    """
    Anthropic Claude API를 모방하는 Mock 클라이언트.
    messages.create() 인터페이스를 그대로 구현합니다.
    """

    def __init__(self):
        self.messages = _MockMessages()


class _MockMessages:
    """claude_client.messages.create(...)를 흉내 냅니다."""

    # QA 호출 횟수를 인스턴스마다 추적
    _qa_call_count: int = 0

    def create(self, model: str, max_tokens: int, messages: list) -> _MockMessage:
        prompt = messages[0]["content"] if messages else ""

        # ── Planner 응답 ──────────────────────────────────────────────
        if "Break down the following task into a step-by-step plan" in prompt:
            return _MockMessage(self._planner_response(prompt))

        # ── Coder 응답 ────────────────────────────────────────────────
        if "Write Python code" in prompt or "Rewrite the code" in prompt:
            has_feedback = "Previous QA Feedback" in prompt
            return _MockMessage(self._coder_response(prompt, has_feedback))

        # ── QA 응답 ───────────────────────────────────────────────────
        if "You are a strict code reviewer" in prompt:
            self._qa_call_count += 1
            return _MockMessage(self._qa_response(self._qa_call_count))

        # 알 수 없는 프롬프트
        return _MockMessage("(mock) 응답을 생성했습니다.")

    # ── 내부 응답 생성 메서드 ─────────────────────────────────────────

    @staticmethod
    def _planner_response(prompt: str) -> str:
        return textwrap.dedent("""\
            Step 1: Understand the requirements and define input/output format.
            Step 2: Design the data structures needed (e.g., classes, dicts).
            Step 3: Implement the core logic with proper function decomposition.
            Step 4: Add input validation and error handling.
            Step 5: Write basic test cases to verify correctness.
            Step 6: Refactor for readability and add docstrings.
        """)

    @staticmethod
    def _coder_response(prompt: str, has_feedback: bool) -> str:
        if has_feedback:
            # 피드백 반영 버전 — 에러 핸들링 포함
            return textwrap.dedent("""\
                def calculate_average(numbers):
                    \"\"\"주어진 숫자 목록의 평균을 계산합니다.\"\"\"
                    if not isinstance(numbers, list):
                        raise TypeError("Input must be a list.")
                    if len(numbers) == 0:
                        raise ValueError("Cannot calculate average of an empty list.")
                    if not all(isinstance(n, (int, float)) for n in numbers):
                        raise TypeError("All elements must be numeric.")
                    return sum(numbers) / len(numbers)


                def main():
                    test_cases = [
                        [1, 2, 3, 4, 5],
                        [10, 20, 30],
                        [-1, 0, 1],
                    ]
                    for case in test_cases:
                        result = calculate_average(case)
                        print(f"Average of {case} = {result}")

                    # Edge case tests
                    try:
                        calculate_average([])
                    except ValueError as e:
                        print(f"[Edge case] Empty list → {e}")

                    try:
                        calculate_average("not a list")
                    except TypeError as e:
                        print(f"[Edge case] Non-list input → {e}")


                if __name__ == "__main__":
                    main()
            """)
        else:
            # 초기 버전 — 에러 핸들링 없음 (QA에서 지적될 예정)
            return textwrap.dedent("""\
                def calculate_average(numbers):
                    \"\"\"주어진 숫자 목록의 평균을 계산합니다.\"\"\"
                    return sum(numbers) / len(numbers)


                def main():
                    numbers = [1, 2, 3, 4, 5]
                    result = calculate_average(numbers)
                    print(f"Average: {result}")


                if __name__ == "__main__":
                    main()
            """)

    @staticmethod
    def _qa_response(call_count: int) -> str:
        if call_count <= 1:
            # 첫 번째 리뷰 → 실패
            result = {
                "passed": False,
                "feedback": (
                    "The code does not handle edge cases such as empty lists or "
                    "non-numeric inputs. This will cause ZeroDivisionError and "
                    "TypeError at runtime."
                ),
                "issues": [
                    "No check for empty list — causes ZeroDivisionError",
                    "No type validation for list elements",
                    "No input validation (non-list input is not handled)",
                    "Missing docstring for main function",
                ],
            }
        else:
            # 두 번째 이상 리뷰 → 통과
            result = {
                "passed": True,
                "feedback": (
                    "The code now properly handles edge cases and includes "
                    "type validation. Logic is correct and readable."
                ),
                "issues": [],
            }
        return json.dumps(result, indent=2)
