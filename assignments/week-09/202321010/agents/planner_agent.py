"""
PlannerAgent

주어진 태스크를 단계별 계획(plan)으로 변환합니다.
Claude API를 사용하며, 실제 API 키가 없을 경우 MockClaudeClient로 대체됩니다.
"""

import logging

logger = logging.getLogger(__name__)


class PlannerAgent:
    """태스크를 받아 단계별 실행 계획을 생성하는 에이전트."""

    def __init__(self, claude_client):
        """
        Args:
            claude_client: anthropic.Anthropic() 또는 MockClaudeClient 인스턴스.
        """
        self.claude_client = claude_client

    def run(self, task: str) -> str:
        """
        태스크를 분석하여 실행 계획을 반환합니다.

        Args:
            task: 수행할 작업 설명 문자열.

        Returns:
            단계별 계획 문자열.
        """
        logger.info("[Planner] Generating plan for task: %s", task)

        prompt = f"""You are an expert software architect.
Break down the following task into a step-by-step plan for a developer to implement.
Be concise but complete.

Task:
{task}

Return a numbered list of implementation steps only.
"""

        response = self.claude_client.messages.create(
            model="claude-3-5-sonnet-latest",
            max_tokens=500,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )

        plan = response.content[0].text.strip()
        logger.info("[Planner] Plan generated:\n%s", plan)
        return plan
