"""Planner → Coder → QA 파이프라인 통합"""
from agents.planner_agent import PlannerAgent
from agents.coder_agent import CoderAgent
from agents.qa_agent import QAAgent
from feedback_loop import enqueue_fix_task
import json
from pathlib import Path
import sys


MAX_QA_ITERATIONS = 3


def update_state(**kwargs):
    """파이프라인 상태를 pipeline-state.json에 저장"""
    path = Path("pipeline-state.json")

    if path.exists():
        state = json.loads(path.read_text(encoding="utf-8"))
    else:
        state = {}

    state.update(kwargs)

    path.write_text(
        json.dumps(state, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )


def main():
    """메인 파이프라인 실행"""
    print("=" * 60)
    print("🚀 Multi-Agent Pipeline 시작")
    print("=" * 60)
    
    # 에이전트 초기화
    planner = PlannerAgent()
    coder = CoderAgent()
    
    try:
        qa = QAAgent()
    except ValueError as e:
        print(f"\n❌ QAAgent 초기화 실패: {e}")
        print("\n💡 ANTHROPIC_API_KEY 환경변수를 설정하세요:")
        print("   Windows: $env:ANTHROPIC_API_KEY='your-api-key'")
        print("   Linux/Mac: export ANTHROPIC_API_KEY='your-api-key'")
        sys.exit(1)

    # [1] Planner 단계
    print("\n" + "=" * 60)
    print("📋 [STEP 1] Planner Agent")
    print("=" * 60)
    planner.run("requirements.md")
    update_state(current_phase="planner_done")

    # [2] Coder 단계
    print("\n" + "=" * 60)
    print("💻 [STEP 2] Coder Agent")
    print("=" * 60)
    coder.run("task_queue.json")
    update_state(current_phase="coder_done")

    # [3] QA 단계 (최대 3회 반복)
    for i in range(1, MAX_QA_ITERATIONS + 1):
        print("\n" + "=" * 60)
        print(f"🔍 [STEP 3] QA Agent - Iteration {i}/{MAX_QA_ITERATIONS}")
        print("=" * 60)

        review_result = qa.review_pr(test_dir="tests")
        update_state(
            current_phase="qa_done",
            qa_iteration_count=i,
            last_qa_approved=review_result["approved"]
        )

        if review_result["approved"]:
            print("\n" + "=" * 60)
            print("✅ QA PASS - 파이프라인 성공!")
            print("=" * 60)
            update_state(final_status="PASS")
            print_summary(review_result)
            return

        print("\n" + "=" * 60)
        print("❌ QA FAIL - Coder 재실행 필요")
        print("=" * 60)
        print(f"  실패 사유: {review_result['review'].get('feedback_for_coder', 'Unknown')}")
        
        enqueue_fix_task(review_result)

        if i == MAX_QA_ITERATIONS:
            print("\n" + "=" * 60)
            print("🚨 3회 실패: Human Intervention 필요")
            print("=" * 60)
            update_state(
                final_status="FAIL",
                human_intervention=True
            )
            print_summary(review_result)
            return

        print("\n" + "=" * 60)
        print(f"🔄 [STEP 4] Coder Agent 재실행 - Iteration {i}")
        print("=" * 60)
        coder.run("task_queue.json")

    print("\n" + "=" * 60)
    print("Pipeline finished")
    print("=" * 60)


def print_summary(review_result):
    """최종 결과 요약 출력"""
    print("\n📊 최종 결과 요약")
    print("-" * 60)
    print(f"  테스트 통과: {review_result['tests_passed']}")
    print(f"  QA 승인: {review_result['approved']}")
    
    scores = review_result['review']['scores']
    print(f"\n  점수:")
    for key, value in scores.items():
        print(f"    - {key}: {value}/10")
    
    critical = review_result['review']['critical_issues']
    if critical:
        print(f"\n  Critical 이슈: {len(critical)}개")
        for issue in critical:
            print(f"    - {issue}")
    else:
        print(f"\n  Critical 이슈: 없음")
    
    print("-" * 60)
    print(f"\n📁 생성된 파일:")
    print(f"  - architecture.md")
    print(f"  - task_queue.json")
    print(f"  - pipeline-state.json")
    print(f"  - review-results.json")
    print(f"  - src/calculator.py")
    print(f"  - tests/test_calculator.py")


if __name__ == "__main__":
    main()
