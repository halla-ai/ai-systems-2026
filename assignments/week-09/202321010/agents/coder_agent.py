"""
CoderAgent

Planner가 생성한 계획을 바탕으로 Python 코드를 작성합니다.
QA 피드백이 있을 경우 이전 코드의 문제를 수정하여 재생성합니다.
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)


class CoderAgent:
    """계획(plan)과 선택적 QA 피드백을 받아 Python 코드를 생성하는 에이전트."""

    def __init__(self, claude_client):
        """
        Args:
            claude_client: anthropic.Anthropic() 또는 MockClaudeClient 인스턴스.
        """
        self.claude_client = claude_client

    def run(
        self,
        task: str,
        plan: str,
        feedback: Optional[str] = None,
        previous_code: Optional[str] = None,
    ) -> str:
        """
        태스크와 계획을 기반으로 코드를 생성합니다.
        피드백이 있으면 이전 코드의 문제점을 수정합니다.

        Args:
            task: 수행할 작업 설명.
            plan: PlannerAgent가 생성한 단계별 계획.
            feedback: QAAgent가 반환한 수정 피드백 (재시도 시 전달).
            previous_code: 이전에 생성된 코드 (재시도 시 참고용).

        Returns:
            생성된 Python 코드 문자열.
        """
        if feedback:
            logger.info("[Coder] Regenerating code with QA feedback")
            prompt = self._build_retry_prompt(task, plan, feedback, previous_code)
        else:
            logger.info("[Coder] Generating initial code")
            prompt = self._build_initial_prompt(task, plan)

        response = self.claude_client.messages.create(
            model="claude-3-5-sonnet-latest",
            max_tokens=1500,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )

        code = response.content[0].text.strip()
        logger.info("[Coder] Code generated (%d chars)", len(code))
        return code

    # ── 프롬프트 빌더 ──────────────────────────────────────────────────

    @staticmethod
    def _build_initial_prompt(task: str, plan: str) -> str:
        return f"""You are an expert Python developer.
Write Python code that implements the following task according to the given plan.

Task:
{task}

Plan:
{plan}

Requirements:
- Write clean, readable Python code.
- Follow the plan step by step.
- Return only the code, no explanations.
"""

    @staticmethod
    def _build_retry_prompt(
        task: str,
        plan: str,
        feedback: str,
        previous_code: Optional[str],
    ) -> str:
        previous_section = (
            f"\nPrevious Code:\n{previous_code}\n" if previous_code else ""
        )
        return f"""You are an expert Python developer.
Rewrite the code to fix all issues identified in the QA feedback.

Task:
{task}

Plan:
{plan}
{previous_section}
Previous QA Feedback:
{feedback}

Requirements:
- Fix every issue mentioned in the feedback.
- Keep the parts that were already correct.
- Return only the corrected code, no explanations.
"""
