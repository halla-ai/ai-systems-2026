# Multi-Agent QA Pipeline - 실행 가이드

## 🚀 빠른 시작

### 1. API 키 설정
```powershell
# Anthropic API 키 설정 (PowerShell)
$env:ANTHROPIC_API_KEY = "sk-ant-your-api-key-here"
```

### 2. 패키지 설치 (이미 완료됨)
```powershell
pip install anthropic pytest
```

### 3. 파이프라인 실행
```powershell
python pipeline.py
```

## 📊 예상 실행 흐름

### 성공 시나리오 (QA 2회 반복 후 성공)

```
============================================================
🚀 Multi-Agent Pipeline 시작
============================================================

============================================================
📋 [STEP 1] Planner Agent
============================================================
- requirements.md 분석
- architecture.md 생성
- task_queue.json 생성 (2개 태스크)

============================================================
💻 [STEP 2] Coder Agent
============================================================
- TASK-001: Calculator 클래스 구현 (버그 포함)
- TASK-002: 단위 테스트 작성

============================================================
🔍 [STEP 3] QA Agent - Iteration 1/3
============================================================
- pytest: FAIL (test_divide_by_zero 실패)
- Claude review: FAIL
  - correctness: 3/10 ⚠️
  - Critical issue: divide_by_zero 예외 처리 누락

❌ QA FAIL → Coder 재실행

============================================================
🔄 [STEP 4] Coder Agent 재실행
============================================================
- FIX-QA-1: divide_by_zero 예외 처리 추가

============================================================
🔍 [STEP 3] QA Agent - Iteration 2/3
============================================================
- pytest: PASS ✅
- Claude review: PASS ✅
  - correctness: 8/10
  - conventions: 7/10
  - test_coverage: 7/10
  - security: 8/10
  - Critical issues: 0

✅ QA PASS - 파이프라인 성공!
```

## 📁 생성될 파일

| 파일 | 설명 | 생성 단계 |
|------|------|----------|
| `architecture.md` | 아키텍처 설계 문서 | Planner |
| `task_queue.json` | 태스크 목록 및 상태 | Planner |
| `src/calculator.py` | Calculator 구현 | Coder |
| `tests/test_calculator.py` | 단위 테스트 | Coder |
| `pipeline-state.json` | 파이프라인 상태 | Pipeline |
| `review-results.json` | QA 리뷰 결과 | QA Agent |

## 🎯 과제 요구사항 충족

### ✅ 1. 완전한 QAAgent 구현
- [x] pytest 자동 실행
- [x] git diff 또는 소스 파일 수집
- [x] Claude API 코드 리뷰
- [x] 4차원 점수 평가
- [x] Critical 이슈 탐지

### ✅ 2. 자동 코드 리뷰 (Claude API)
- [x] `claude-opus-4-20250514` 모델 사용
- [x] correctness, conventions, test_coverage, security 평가
- [x] JSON 형식 응답 파싱

### ✅ 3. 피드백 루프 구현
- [x] QA 실패 시 task_queue에 FIX 태스크 자동 추가
- [x] Coder Agent 자동 재실행
- [x] 최대 3회 재시도 (무한 루프 방지)
- [x] 3회 실패 시 human_intervention 플래그

### ✅ 4. Planner → Coder → QA 파이프라인
- [x] 3단계 파이프라인 완전 자동화
- [x] 상태 추적 (pipeline-state.json)
- [x] 로그 출력 및 결과 요약

## 🔍 의도적 버그 시나리오

프로젝트는 **의도적으로** 1차 구현에 버그를 포함하여 피드백 루프를 시연합니다:

1. **Coder Agent 1차 구현**
   ```python
   def divide(self, a, b):
       # BUG: 예외 처리 없음!
       return a / b
   ```

2. **QA Agent 탐지**
   - pytest: `test_divide_by_zero` 실패
   - Claude: "divide_by_zero 예외 처리 누락" 피드백

3. **Coder Agent 자동 수정**
   ```python
   def divide(self, a, b):
       if b == 0:
           raise ValueError("Cannot divide by zero")
       return a / b
   ```

4. **QA Agent 재검증**
   - pytest: PASS ✅
   - Claude: PASS ✅

## 🛠️ 트러블슈팅

### API 키 오류
```
❌ QAAgent 초기화 실패: ANTHROPIC_API_KEY 환경변수가 설정되지 않았습니다.
```
**해결**: `$env:ANTHROPIC_API_KEY = "sk-ant-..."` 실행

### pytest 찾을 수 없음
```
python: can't open file 'pytest'
```
**해결**: `pip install pytest` 실행

### Claude API 요청 실패
```
anthropic.APIError: 401 Unauthorized
```
**해결**: API 키가 올바른지 확인

## 📚 추가 리소스

- [Anthropic API 문서](https://docs.anthropic.com/)
- [pytest 문서](https://docs.pytest.org/)
- [과제 피드백 원문](피드백 참고)
