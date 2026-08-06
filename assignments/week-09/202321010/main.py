"""
main.py — Lab 09: QA Agent Pipeline

실행 방법:
  python main.py

실제 Claude API 사용 시:
  1. `pip install anthropic` 설치
  2. 아래 USE_MOCK_CLIENT = False 로 변경
  3. ANTHROPIC_API_KEY 환경변수 설정 또는 api_key 직접 입력
"""

import logging
import os
import sys

# ── 로깅 설정 ──────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("pipeline_run.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)

# ── Claude 클라이언트 선택 ─────────────────────────────────────────────
#   실제 API 키가 있을 때: USE_MOCK_CLIENT = False
USE_MOCK_CLIENT = True  # ← API 키 없이 실행할 때 True

if USE_MOCK_CLIENT:
    from mock_claude import MockClaudeClient
    claude = MockClaudeClient()
    logger.info("[Setup] Using MockClaudeClient (no API key required)")
else:
    try:
        import anthropic
        api_key = os.environ.get("ANTHROPIC_API_KEY", "")  # 환경변수에서 읽기
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable is not set.")
        claude = anthropic.Anthropic(api_key=api_key)
        logger.info("[Setup] Using real Anthropic Claude API")
    except ImportError:
        logger.error("[Setup] anthropic package not installed. Run: pip install anthropic")
        sys.exit(1)

# ── 파이프라인 실행 ────────────────────────────────────────────────────
from pipeline import run_pipeline

TASK = (
    "Write a Python function that calculates the average of a list of numbers. "
    "It should handle edge cases like empty lists and non-numeric inputs."
)


def main():
    logger.info("")
    logger.info("╔══════════════════════════════════════════════════════════╗")
    logger.info("║          Lab 09: QA Agent Pipeline Demo                 ║")
    logger.info("╚══════════════════════════════════════════════════════════╝")
    logger.info("")

    final_code = run_pipeline(task=TASK, claude_client=claude)

    logger.info("")
    logger.info("── Final Generated Code ──────────────────────────────────")
    logger.info("%s", final_code)
    logger.info("─────────────────────────────────────────────────────────")
    logger.info("")
    logger.info("[Pipeline] Done. Log saved to pipeline_run.log")


if __name__ == "__main__":
    main()
