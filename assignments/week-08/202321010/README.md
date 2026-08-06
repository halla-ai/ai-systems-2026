# Multi-Agent QA Pipeline

자동 코드 리뷰 및 피드백 루프를 포함한 3단계 에이전트 파이프라인 구현

## 📋 프로젝트 구조

```
202321010/
├── agents/
│   ├── planner_agent.py   # 요구사항 분석 및 태스크 생성
│   ├── coder_agent.py     # 코드 구현 및 수정
│   └── qa_agent.py        # 테스트 실행 + Claude 코드 리뷰
├── src/
│   └── calculator.py      # 구현 코드
├── tests/
│   └── test_calculator.py # 단위 테스트
├── pipeline.py            # 메인 파이프라인
├── feedback_loop.py       # QA 실패 시 재실행 로직
├── requirements.md        # 프로젝트 요구사항
├── architecture.md        # 생성된 아키텍처 문서
├── task_queue.json        # 태스크 큐
├── pipeline-state.json    # 파이프라인 상태
└── review-results.json    # QA 리뷰 결과

## 🚀 실행 방법

### 1. 환경 설정

```powershell
# Python 가상 환경 생성
python -m venv venv

# 가상 환경 활성화 (Windows)
.\venv\Scripts\Activate.ps1

# 필요한 패키지 설치
pip install anthropic pytest
```

### 2. API 키 설정

```powershell
# Anthropic API 키 환경변수 설정
$env:ANTHROPIC_API_KEY = "your-api-key-here"
```

### 3. 파이프라인 실행

```powershell
python pipeline.py
```

## 🔄 파이프라인 흐름

```
1. Planner Agent
   └─→ requirements.md 분석
   └─→ architecture.md 생성
   └─→ task_queue.json 생성

2. Coder Agent
   └─→ task_queue 읽기
   └─→ 코드 구현 (src/calculator.py)
   └─→ 테스트 작성 (tests/test_calculator.py)

3. QA Agent (최대 3회 반복)
   ├─→ pytest 실행
   ├─→ git diff 수집
   ├─→ Claude API 코드 리뷰
   ├─→ 최종 판정
   │
   ├─→ PASS? → ✅ 완료
   └─→ FAIL? → ❌ Coder 재실행
       └─→ feedback_loop.py
           └─→ task_queue에 FIX 태스크 추가
           └─→ 2번으로 돌아감
```

## 📊 QA 평가 기준

### PASS 조건
- ✅ 모든 테스트 통과
- ✅ 4가지 점수 모두 4점 이상
  - `correctness` (정확성)
  - `conventions` (코딩 규칙)
  - `test_coverage` (테스트 커버리지)
  - `security` (보안)
- ✅ Critical 이슈 0개

## 🎯 구현 특징

### 1. QAAgent 완전 구현
- pytest 자동 실행
- Claude API 기반 코드 리뷰
- 4차원 점수 평가 (0-10점)
- Critical 이슈 탐지

### 2. 피드백 루프
- QA 실패 시 자동으로 task_queue에 수정 태스크 추가
- Coder Agent가 자동으로 재실행
- 최대 3회 재시도 (무한 루프 방지)

### 3. 의도적 버그 시나리오
- **1차 구현**: divide_by_zero 예외 처리 누락
- **QA 탐지**: 테스트 실패 + Claude 리뷰 FAIL
- **자동 수정**: Coder Agent가 예외 처리 추가
- **재검증**: QA Agent 재실행 → PASS

## 📝 생성 파일

| 파일 | 설명 |
|------|------|
| `architecture.md` | Planner가 생성한 아키텍처 문서 |
| `task_queue.json` | 태스크 목록 및 상태 |
| `pipeline-state.json` | 파이프라인 진행 상태 |
| `review-results.json` | QA 리뷰 상세 결과 |
| `src/calculator.py` | 구현 코드 |
| `tests/test_calculator.py` | 단위 테스트 |

## 🔍 로그 예시

```
============================================================
🚀 Multi-Agent Pipeline 시작
============================================================

============================================================
📋 [STEP 1] Planner Agent
============================================================

=== Planner Agent 시작 ===
  → requirements.md 분석 완료
  → architecture.md 생성 완료
  → task_queue.json 생성 완료 (2개 태스크)
=== Planner Agent 종료 ===

============================================================
💻 [STEP 2] Coder Agent
============================================================

=== Coder Agent 시작 ===
  → 태스크 처리 중: TASK-001 - Calculator 클래스 구현
    • Calculator 클래스 구현 중...
    ✓ src/calculator.py 생성 완료
  → 태스크 처리 중: TASK-002 - 단위 테스트 작성
    • 단위 테스트 작성 중...
    ✓ tests/test_calculator.py 생성 완료
=== Coder Agent 종료 ===

============================================================
🔍 [STEP 3] QA Agent - Iteration 1/3
============================================================

=== QA Agent 시작 ===
  → pytest 실행 중: tests
  → 테스트 결과: FAIL
  → git diff 수집 중
  → Claude API 코드 리뷰 요청 중...
  → 리뷰 완료: FAIL
  → 최종 판정: REJECTED ❌
=== QA Agent 종료 ===

============================================================
❌ QA FAIL - Coder 재실행 필요
============================================================
  실패 사유: divide_by_zero 예외 처리가 누락되었습니다.
  → task_queue에 FIX-QA-1 추가 완료

============================================================
🔄 [STEP 4] Coder Agent 재실행 - Iteration 1
============================================================

=== Coder Agent 시작 ===
  → 태스크 처리 중: FIX-QA-1 - fix_qa_failure
    • QA 피드백 반영 중...
    • Calculator 클래스 구현 중...
    ✓ src/calculator.py 생성 완료
    ✓ divide_by_zero 예외 처리 추가 완료
=== Coder Agent 종료 ===

============================================================
🔍 [STEP 3] QA Agent - Iteration 2/3
============================================================

=== QA Agent 시작 ===
  → pytest 실행 중: tests
  → 테스트 결과: PASS
  → git diff 수집 중
  → Claude API 코드 리뷰 요청 중...
  → 리뷰 완료: PASS
  → 최종 판정: APPROVED ✅
=== QA Agent 종료 ===

============================================================
✅ QA PASS - 파이프라인 성공!
============================================================

📊 최종 결과 요약
------------------------------------------------------------
  테스트 통과: True
  QA 승인: True

  점수:
    - correctness: 8/10
    - conventions: 7/10
    - test_coverage: 7/10
    - security: 8/10

  Critical 이슈: 없음
------------------------------------------------------------
```

## 📚 참고

- Claude API: `claude-opus-4-20250514`
- pytest 문서: https://docs.pytest.org/
- Anthropic API 문서: https://docs.anthropic.com/
