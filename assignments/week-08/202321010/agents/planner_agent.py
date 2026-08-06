"""PlannerAgent: requirements를 분석하고 task queue를 생성"""
import json
from pathlib import Path


class PlannerAgent:
    def __init__(self):
        pass

    def run(self, requirements_file="requirements.md"):
        """requirements.md를 읽고 architecture.md와 task_queue.json 생성"""
        print("\n=== Planner Agent 시작 ===")
        
        # requirements.md 읽기
        req_path = Path(requirements_file)
        if not req_path.exists():
            raise FileNotFoundError(f"{requirements_file}이 존재하지 않습니다.")
        
        requirements = req_path.read_text(encoding="utf-8")
        print(f"  → {requirements_file} 분석 완료")
        
        # architecture.md 생성
        architecture = self._generate_architecture(requirements)
        Path("architecture.md").write_text(architecture, encoding="utf-8")
        print("  → architecture.md 생성 완료")
        
        # task_queue.json 생성
        tasks = self._generate_tasks(requirements)
        Path("task_queue.json").write_text(
            json.dumps(tasks, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )
        print(f"  → task_queue.json 생성 완료 ({len(tasks)}개 태스크)")
        print("=== Planner Agent 종료 ===\n")
        
        return tasks

    def _generate_architecture(self, requirements):
        """간단한 아키텍처 문서 생성"""
        return f"""# 아키텍처 설계

## 요구사항 요약
{requirements[:200]}...

## 시스템 구조
```
src/
  calculator.py  # 계산기 핵심 로직
tests/
  test_calculator.py  # 단위 테스트
```

## 주요 컴포넌트
1. Calculator 클래스: 기본 산술 연산 제공
2. 예외 처리: divide_by_zero 등

## 테스트 전략
- 각 연산마다 단위 테스트 작성
- 엣지 케이스(0으로 나누기 등) 테스트
"""

    def _generate_tasks(self, requirements):
        """요구사항 기반 태스크 생성"""
        return [
            {
                "id": "TASK-001",
                "type": "implementation",
                "priority": "HIGH",
                "status": "pending",
                "title": "Calculator 클래스 구현",
                "description": "add, subtract, multiply, divide 메서드를 가진 Calculator 클래스 구현",
                "acceptance_criteria": [
                    "add(a, b) 구현",
                    "subtract(a, b) 구현",
                    "multiply(a, b) 구현",
                    "divide(a, b) 구현 (0으로 나누기 예외 처리 포함)"
                ]
            },
            {
                "id": "TASK-002",
                "type": "testing",
                "priority": "HIGH",
                "status": "pending",
                "title": "단위 테스트 작성",
                "description": "Calculator 클래스의 모든 기능에 대한 테스트 작성",
                "acceptance_criteria": [
                    "각 연산에 대한 정상 케이스 테스트",
                    "엣지 케이스 테스트 (0으로 나누기 등)"
                ]
            }
        ]
