"""
QAAgent

CoderAgent가 생성한 코드를 Claude API로 리뷰하여
통과 여부(passed), 피드백(feedback), 이슈 목록(issues)을 반환합니다.
"""

import json
import logging
from dataclasses import dataclass, field
from typing import List

logger = logging.getLogger(__name__)


@dataclass
class QAResult:
    """QA 리뷰 결과를 담는 데이터 클래스."""

    passed: bool
    feedback: str
    issues: List[str] = field(default_factory=list)

    def __str__(self) -> str:
        status = "PASSED" if self.passed else "FAILED"
        lines = [f"[QA Result] {status}", f"  Feedback : {self.feedback}"]
        if self.issues:
            lines.append("  Issues   :")
            for issue in self.issues:
                lines.append(f"    - {issue}")
        return "\n".join(lines)


class QAAgent:
    """코드 리뷰를 담당하는 QA 에이전트."""

    def __init__(self, claude_client):
        """
        Args:
            claude_client: anthropic.Anthropic() 또는 MockClaudeClient 인스턴스.
        """
        self.claude_client = claude_client

    def review_code(self, task: str, plan: str, code: str) -> QAResult:
        """
        코드를 리뷰하고 QAResult를 반환합니다.

        Args:
            task: 원래 수행해야 할 작업 설명.
            plan: PlannerAgent가 생성한 계획.
            code: CoderAgent가 생성한 Python 코드.

        Returns:
            QAResult(passed, feedback, issues)
        """
        logger.info("[QA] Review started")

        prompt = f"""You are a strict code reviewer.

Task:
{task}

Plan:
{plan}

Code:
{code}

Review the code against the following criteria:
1. Does the code fully satisfy the task requirements?
2. Are there any bugs or runtime errors?
3. Is the overall design reasonable and maintainable?
4. Are edge cases (empty input, invalid types, boundary values) handled?

Return ONLY a valid JSON object in the following format (no markdown, no extra text):
{{
  "passed": true or false,
  "feedback": "concise summary of findings",
  "issues": ["issue description 1", "issue description 2"]
}}
"""

        response = self.claude_client.messages.create(
            model="claude-3-5-sonnet-latest",
            max_tokens=1000,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )

        raw_text = response.content[0].text.strip()
        return self._parse_response(raw_text)

    # ── 내부 파싱 ──────────────────────────────────────────────────────

    @staticmethod
    def _parse_response(raw_text: str) -> QAResult:
        """Claude 응답 JSON을 QAResult로 변환합니다."""
        try:
            data = json.loads(raw_text)
            passed = bool(data.get("passed", False))
            feedback = str(data.get("feedback", ""))
            issues = list(data.get("issues", []))

            if passed:
                logger.info("[QA] Passed: %s", feedback)
            else:
                logger.warning("[QA] Failed: %s", feedback)
                for issue in issues:
                    logger.warning("[QA]   Issue: %s", issue)

            return QAResult(passed=passed, feedback=feedback, issues=issues)

        except (json.JSONDecodeError, KeyError, TypeError) as exc:
            logger.error("[QA] Failed to parse response: %s | raw: %s", exc, raw_text)
            # 파싱 실패 시 안전하게 실패 처리
            return QAResult(
                passed=False,
                feedback=f"QA response parsing error: {exc}",
                issues=["Could not parse QA response as JSON"],
            )
