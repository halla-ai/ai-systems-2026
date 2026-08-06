# Lab 09: QA Agent Pipeline

Planner → Coder → QA 3단계 파이프라인 구현.  
QA가 실패하면 피드백을 Coder에 전달하여 코드를 재생성하는 피드백 루프를 포함합니다.

---

## ⚠️ Claude API 미설정 안내

현재 **Anthropic Claude API 키가 없는 상태**입니다.  
실제 API 대신 `mock_claude.py`의 `MockClaudeClient`를 사용하며,  
Claude API와 동일한 인터페이스(`messages.create(...)`)로 동작합니다.

실제 API 연결 방법은 [실제 API 사용](#실제-claude-api-사용-시) 섹션을 참고하세요.

---

## 프로젝트 구조

```
202321010/
├── agents/
│   ├── __init__.py
│   ├── planner_agent.py   # 태스크 → 단계별 계획 생성
│   ├── coder_agent.py     # 계획 → 코드 생성 (피드백 반영 재생성 포함)
│   └── qa_agent.py        # 코드 리뷰 → passed / feedback / issues 반환
├── mock_claude.py          # Claude API Mock 클라이언트
├── pipeline.py             # Planner → Coder → QA 파이프라인 + 피드백 루프
├── main.py                 # 진입점
├── pipeline_run.log        # 실행 시 자동 생성되는 로그 파일
└── requirements.txt
```

---

## 파이프라인 흐름

```
User Task
  ↓
PlannerAgent       — 태스크를 단계별 계획으로 분해
  ↓
CoderAgent         — 계획을 바탕으로 Python 코드 생성
  ↓
QAAgent            — 코드 리뷰 (passed / feedback / issues 반환)
  ↓
passed == True  → 완료
passed == False → 피드백을 CoderAgent에 전달 → 코드 재생성 (최대 3회)
```

---

## 실행 방법

```bash
python main.py
```

실행 결과는 콘솔과 `pipeline_run.log` 파일에 동시에 기록됩니다.

### 실행 로그 예시

```
[Planner] Plan generated
[Coder] Code generated
[QA] Review started
[QA] Failed: missing error handling
[QA]   Issue: No check for empty list — causes ZeroDivisionError
[QA]   Issue: No type validation for list elements
[Coder] Regenerating code with QA feedback
[QA] Review started
[QA] Passed
[Pipeline] Completed successfully on attempt 2
```

---

## 실제 Claude API 사용 시

1. 패키지 설치

```bash
pip install anthropic
```

2. API 키 환경변수 설정

```bash
# Windows PowerShell
$env:ANTHROPIC_API_KEY = "sk-ant-..."

# Windows CMD
set ANTHROPIC_API_KEY=sk-ant-...
```

3. `main.py` 수정

```python
# 변경 전
USE_MOCK_CLIENT = True

# 변경 후
USE_MOCK_CLIENT = False
```

4. 실행

```bash
python main.py
```

---

## 요구사항 충족 현황

| 요구사항 | 구현 위치 | 상태 |
|---------|----------|------|
| 완전한 QAAgent 구현 | `agents/qa_agent.py` | ✅ |
| 자동 코드 리뷰 (Claude API) | `qa_agent.py` — `messages.create(...)` | ✅ (Mock 대체) |
| 피드백 루프 (QA 실패 → Coder 재실행) | `pipeline.py` | ✅ |
| End-to-end 시연 로그 | `pipeline_run.log` | ✅ |
