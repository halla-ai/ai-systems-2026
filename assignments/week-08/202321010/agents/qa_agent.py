"""QAAgent: 테스트 실행 및 Claude 코드 리뷰 수행"""
import json
import subprocess
from pathlib import Path
import anthropic
import os


class QAAgent:
    def __init__(self, model="claude-opus-4-20250514"):
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY 환경변수가 설정되지 않았습니다.")
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model

    def run_tests(self, test_dir="tests"):
        """pytest를 실행하고 결과를 반환"""
        print(f"  → pytest 실행 중: {test_dir}")
        
        result = subprocess.run(
            ["python", "-m", "pytest", test_dir, "-v", "--tb=short"],
            capture_output=True,
            text=True
        )

        return {
            "passed": result.returncode == 0,
            "stdout": result.stdout,
            "stderr": result.stderr
        }

    def get_git_diff(self):
        """git diff를 가져오거나, git이 없으면 소스 파일 내용을 반환"""
        print("  → git diff 수집 중")
        
        # git이 없을 경우를 대비해 소스 파일을 직접 읽음
        result = subprocess.run(
            ["git", "diff", "--", "."],
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout
        
        # git diff가 비어있거나 git이 없으면 소스 파일을 직접 수집
        print("  → git diff가 비어있음, 소스 파일 직접 수집")
        source_files = []
        for py_file in Path(".").rglob("*.py"):
            if "tests" not in str(py_file) and "__pycache__" not in str(py_file):
                try:
                    content = py_file.read_text(encoding="utf-8")
                    source_files.append(f"=== {py_file} ===\n{content}\n")
                except Exception as e:
                    print(f"  ! 파일 읽기 실패: {py_file} - {e}")
        
        return "\n".join(source_files) if source_files else "No source files found"

    def code_review(self, diff, test_output):
        """Claude API를 사용해 코드 리뷰 수행"""
        print("  → Claude API 코드 리뷰 요청 중...")
        
        prompt = f"""
다음 코드 diff와 테스트 결과를 독립 QA 관점에서 리뷰하라.

검토 기준 (각 0-10점):
1. correctness: 기능이 정확히 동작하는가? 로직 오류가 없는가?
2. conventions: 코딩 스타일과 명명 규칙을 따르는가?
3. test_coverage: 테스트가 충분한가? 엣지 케이스를 다루는가?
4. security: 보안 취약점이 없는가? 입력 검증이 적절한가?

**중요: 반드시 순수 JSON만 출력하라. 마크다운 코드 블록(```)이나 다른 텍스트 없이 JSON만 반환하라.**

출력 형식:
{{
  "scores": {{
    "correctness": 0,
    "conventions": 0,
    "test_coverage": 0,
    "security": 0
  }},
  "critical_issues": [],
  "issues": [],
  "verdict": "PASS or FAIL",
  "feedback_for_coder": "string"
}}

PASS 기준: 모든 점수 4점 이상 + critical_issues가 비어있음

코드 diff:
{diff}

테스트 결과:
{test_output}
"""

        response = self.client.messages.create(
            model=self.model,
            max_tokens=2048,
            system="당신은 코드 수정 권한이 없는 독립 QA 에이전트다. 오직 리뷰와 판정만 수행한다. 반드시 순수 JSON만 출력하고 다른 텍스트는 포함하지 마라.",
            messages=[{"role": "user", "content": prompt}]
        )

        # Claude 응답에서 JSON 추출
        response_text = response.content[0].text.strip()
        
        # 마크다운 코드 블록 제거
        if response_text.startswith("```"):
            lines = response_text.split("\n")
            # 첫 줄과 마지막 줄 제거
            response_text = "\n".join(lines[1:-1])
        
        try:
            review_data = json.loads(response_text)
        except json.JSONDecodeError as e:
            print(f"  ! JSON 파싱 실패: {e}")
            print(f"  ! 응답: {response_text[:200]}...")
            # 기본 응답 반환
            review_data = {
                "scores": {
                    "correctness": 0,
                    "conventions": 0,
                    "test_coverage": 0,
                    "security": 0
                },
                "critical_issues": ["JSON 파싱 실패"],
                "issues": [],
                "verdict": "FAIL",
                "feedback_for_coder": f"Claude 응답을 파싱할 수 없습니다: {response_text[:100]}"
            }
        
        print(f"  → 리뷰 완료: {review_data.get('verdict', 'UNKNOWN')}")
        return review_data

    def judge(self, review, tests_passed):
        """최종 판정: 테스트 + 점수 + Critical 이슈 확인"""
        scores = review["scores"]
        score_passed = all(v >= 4 for v in scores.values())
        no_critical = len(review["critical_issues"]) == 0

        return tests_passed and score_passed and no_critical

    def review_pr(self, test_dir="tests"):
        """전체 QA 프로세스 실행"""
        print("\n=== QA Agent 시작 ===")
        
        # 1. 테스트 실행
        test_result = self.run_tests(test_dir)
        print(f"  → 테스트 결과: {'PASS' if test_result['passed'] else 'FAIL'}")
        
        # 2. 코드 diff 수집
        diff = self.get_git_diff()
        
        # 3. Claude 코드 리뷰
        review = self.code_review(
            diff=diff,
            test_output=test_result["stdout"] + "\n" + test_result["stderr"]
        )
        
        # 4. 최종 판정
        approved = self.judge(review, test_result["passed"])
        
        result = {
            "tests_passed": test_result["passed"],
            "approved": approved,
            "test_result": test_result,
            "review": review
        }
        
        # 5. 결과 저장
        Path("review-results.json").write_text(
            json.dumps(result, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )
        
        print(f"  → 최종 판정: {'APPROVED ✅' if approved else 'REJECTED ❌'}")
        print("=== QA Agent 종료 ===\n")
        
        return result
