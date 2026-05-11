"""CoderAgent: task queue를 읽고 코드 구현"""
import json
from pathlib import Path


class CoderAgent:
    def __init__(self):
        pass

    def run(self, task_queue_file="task_queue.json"):
        """task_queue.json을 읽고 pending 태스크 실행"""
        print("\n=== Coder Agent 시작 ===")
        
        queue_path = Path(task_queue_file)
        if not queue_path.exists():
            print(f"  ! {task_queue_file}이 존재하지 않습니다.")
            return
        
        tasks = json.loads(queue_path.read_text(encoding="utf-8"))
        
        for task in tasks:
            if task["status"] == "pending":
                print(f"  → 태스크 처리 중: {task['id']} - {task['title']}")
                self._execute_task(task)
                task["status"] = "completed"
        
        # 업데이트된 task_queue 저장
        queue_path.write_text(
            json.dumps(tasks, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )
        
        print("=== Coder Agent 종료 ===\n")

    def _execute_task(self, task):
        """개별 태스크 실행"""
        task_type = task.get("type", "")
        task_id = task["id"]
        
        if task_type == "implementation":
            self._implement_code(task)
        elif task_type == "testing":
            self._write_tests(task)
        elif task_type == "fix_qa_failure":
            self._fix_qa_issues(task)
        else:
            print(f"    ! 알 수 없는 태스크 타입: {task_type}")

    def _implement_code(self, task):
        """코드 구현 (Calculator 예제)"""
        print(f"    • Calculator 클래스 구현 중...")
        
        # 첫 번째 구현: 의도적으로 divide_by_zero 예외 처리 누락
        if task["id"] == "TASK-001" and not Path("src/calculator.py").exists():
            calculator_code = '''"""간단한 계산기 구현"""


class Calculator:
    """기본 산술 연산을 제공하는 계산기"""
    
    def add(self, a, b):
        """덧셈"""
        return a + b
    
    def subtract(self, a, b):
        """뺄셈"""
        return a - b
    
    def multiply(self, a, b):
        """곱셈"""
        return a * b
    
    def divide(self, a, b):
        """나눗셈 - 초기 구현 (예외 처리 누락)"""
        # BUG: divide_by_zero 예외 처리가 없음!
        return a / b
'''
        else:
            # QA 피드백 후 수정 버전
            calculator_code = '''"""간단한 계산기 구현 - 수정 버전"""


class Calculator:
    """기본 산술 연산을 제공하는 계산기"""
    
    def add(self, a, b):
        """덧셈"""
        return a + b
    
    def subtract(self, a, b):
        """뺄셈"""
        return a - b
    
    def multiply(self, a, b):
        """곱셈"""
        return a * b
    
    def divide(self, a, b):
        """나눗셈 - 0으로 나누기 예외 처리 추가"""
        if b == 0:
            raise ValueError("Cannot divide by zero")
        return a / b
'''
        
        Path("src").mkdir(exist_ok=True)
        Path("src/calculator.py").write_text(calculator_code, encoding="utf-8")
        Path("src/__init__.py").write_text("", encoding="utf-8")
        print(f"    ✓ src/calculator.py 생성 완료")

    def _write_tests(self, task):
        """테스트 코드 작성"""
        print(f"    • 단위 테스트 작성 중...")
        
        test_code = '''"""Calculator 단위 테스트"""
import pytest
from src.calculator import Calculator


def test_add():
    """덧셈 테스트"""
    calc = Calculator()
    assert calc.add(2, 3) == 5
    assert calc.add(-1, 1) == 0
    assert calc.add(0, 0) == 0


def test_subtract():
    """뺄셈 테스트"""
    calc = Calculator()
    assert calc.subtract(5, 3) == 2
    assert calc.subtract(0, 5) == -5


def test_multiply():
    """곱셈 테스트"""
    calc = Calculator()
    assert calc.multiply(3, 4) == 12
    assert calc.multiply(-2, 3) == -6
    assert calc.multiply(0, 100) == 0


def test_divide():
    """나눗셈 테스트"""
    calc = Calculator()
    assert calc.divide(10, 2) == 5
    assert calc.divide(7, 2) == 3.5


def test_divide_by_zero():
    """0으로 나누기 예외 테스트"""
    calc = Calculator()
    with pytest.raises(ValueError, match="Cannot divide by zero"):
        calc.divide(10, 0)
'''
        
        Path("tests").mkdir(exist_ok=True)
        Path("tests/__init__.py").write_text("", encoding="utf-8")
        Path("tests/test_calculator.py").write_text(test_code, encoding="utf-8")
        print(f"    ✓ tests/test_calculator.py 생성 완료")

    def _fix_qa_issues(self, task):
        """QA 피드백 기반 수정"""
        print(f"    • QA 피드백 반영 중...")
        feedback = task.get("feedback_for_coder", "")
        
        # divide_by_zero 예외 처리 추가
        if "divide" in feedback.lower() or "zero" in feedback.lower():
            # 수정된 Calculator 코드 작성
            self._implement_code({"id": "FIX", "type": "implementation"})
            print(f"    ✓ divide_by_zero 예외 처리 추가 완료")
