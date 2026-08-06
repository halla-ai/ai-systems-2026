"""
Pipeline

Planner → Coder → QA 3단계 파이프라인.
QA가 실패하면 최대 MAX_RETRIES 횟수만큼 Coder를 재실행합니다.
"""

import logging
from typing import Optional

from agents import PlannerAgent, CoderAgent, QAAgent

logger = logging.getLogger(__name__)

MAX_RETRIES = 3


def run_pipeline(task: str, claude_client) -> Optional[str]:
    """
    Planner → Coder → QA 파이프라인을 실행합니다.

    Args:
        task: 수행할 작업 설명 문자열.
        claude_client: anthropic.Anthropic() 또는 MockClaudeClient 인스턴스.

    Returns:
        최종 생성된 코드 문자열. MAX_RETRIES 초과 시에도 마지막 코드를 반환합니다.
    """
    planner = PlannerAgent(claude_client)
    coder = CoderAgent(claude_client)
    qa = QAAgent(claude_client)

    # ── Step 1: Planner ───────────────────────────────────────────────
    logger.info("=" * 60)
    logger.info("[Pipeline] Starting pipeline")
    logger.info("[Pipeline] Task: %s", task)
    logger.info("=" * 60)

    plan = planner.run(task)
    logger.info("[Planner] Plan generated")

    # ── Step 2 & 3: Coder → QA  (피드백 루프) ─────────────────────────
    code: Optional[str] = None
    feedback: Optional[str] = None

    for attempt in range(1, MAX_RETRIES + 1):
        logger.info("-" * 60)
        logger.info("[Pipeline] Attempt %d / %d", attempt, MAX_RETRIES)

        # Coder 실행
        code = coder.run(
            task=task,
            plan=plan,
            feedback=feedback,
            previous_code=code,
        )
        logger.info("[Coder] Code generated")

        # QA 실행
        qa_result = qa.review_code(task=task, plan=plan, code=code)

        if qa_result.passed:
            logger.info("[QA] Passed")
            logger.info("=" * 60)
            logger.info("[Pipeline] Completed successfully on attempt %d", attempt)
            logger.info("=" * 60)
            return code

        # QA 실패 처리
        logger.warning("[QA] Failed: %s", qa_result.feedback)
        for issue in qa_result.issues:
            logger.warning("[QA]   Issue: %s", issue)

        feedback = qa_result.feedback

        if attempt < MAX_RETRIES:
            logger.info("[Coder] Regenerating code with QA feedback")

    # 최대 재시도 횟수 초과
    logger.error("=" * 60)
    logger.error("[Pipeline] Max retries (%d) reached. Returning last code.", MAX_RETRIES)
    logger.error("=" * 60)
    return code
