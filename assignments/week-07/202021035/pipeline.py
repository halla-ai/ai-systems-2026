"""
간단한 Planner→Coder 파이프라인 실행 스크립트.

PlannerAgent는 사용자 목표를 서브태스크로 분해한 계획을 생성하고,
CoderAgent는 생성된 계획을 바탕으로 코드를 수정합니다.

이 스크립트는 교육용 예제로, 실제 코드 수정이나 테스트 수행을 대신하여
에이전트 간의 호출 흐름을 보여 줍니다.
"""

from planner_agent import PlannerAgent
from coder_agent import CoderAgent


def run_pipeline(objective: str, codebase_summary: str = "") -> tuple[dict, dict]:
    """Planner와 Coder를 연쇄 실행하여 계획과 실행 결과를 반환한다."""
    planner = PlannerAgent()
    plan = planner.run({"objective": objective, "codebase_summary": codebase_summary})
    coder = CoderAgent()
    coder_output = coder.run({"plan": plan})
    return plan, coder_output


def main() -> None:
    """명령행에서 파이프라인을 실행하기 위한 진입점."""
    try:
        objective = input("Objective: ").strip()
    except EOFError:
        objective = ""
    try:
        codebase_summary = input("Codebase summary (optional): ").strip()
    except EOFError:
        codebase_summary = ""
    if not objective:
        print("Objective를 입력해야 합니다.")
        return
    plan, coder_output = run_pipeline(objective, codebase_summary)
    print("\n=== Plan ===")
    print(plan)
    print("\n=== Coder Output ===")
    print(coder_output)


if __name__ == "__main__":
    main()