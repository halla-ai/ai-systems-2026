# Week 09: QA Agent Pipeline

## 과제 개요

이 과제는 Planner -> Coder -> QA 3단계 파이프라인을 end-to-end로 실행하는 예제다.  
Week 09의 QA 파이프라인은 Week 08에서 구현한 실제 `PlannerAgent`를 불러와 planning artifact를 먼저 만들고, 그 결과를 바탕으로 Coder와 QA가 피드백 루프를 수행한다.

## 파일별 역할

- `pipeline_e2e.py`: Week 08 PlannerAgent 연동, spec/task 생성, Coder -> QA 루프 실행
- `qa_runner.py`: `pytest` 실행, JSON report/coverage 파싱, 텍스트 fallback
- `code_reviewer.py`: `git diff` 기반 코드 리뷰, API 실패 시 rule-based fallback
- `qa_agent.py`: 테스트 결과와 리뷰 결과를 합쳐 `approve`, `request_changes`, `reject` 판정
- `calculator.py`: Planner와 QA가 함께 참조하는 대상 코드
- `tests/`: 로컬 검증용 pytest 테스트
- `qa_reports/`: iteration별 QA 결과와 최종 pipeline summary JSON

## Week 08 PlannerAgent와의 연결 구조

`pipeline_e2e.py`는 `assignments/week-08/202121014/planner_agent.py`를 동적으로 import한다.  
중요한 점은 PlannerAgent 코드는 Week 08의 구현을 그대로 사용하지만, `project_root`는 Week 09 폴더로 넘겨서 `sample_plan.json`, `spec.md`, `tasks/*.md`, `validation_report.json`이 Week 09 안에 생성되도록 한다.

## spec -> architect -> QA 흐름

이 예제에는 별도 ArchitectAgent 구현은 없지만 흐름은 다음처럼 유지된다.

1. Planner가 요구사항을 분석해 `sample_plan.json`과 `spec.md`를 만든다.
2. Planner가 생성한 task description, acceptance criteria, DAG tier가 구현 맥락이 된다.
3. Coder는 그 planning artifact를 입력으로 받아 코드를 수정한다.
4. QA는 테스트, coverage, 코드 리뷰를 수행하고 피드백을 반환한다.
5. Coder는 피드백을 반영해 다시 시도한다.

즉, Planner가 만든 spec과 task가 이후 단계의 작업 기준점 역할을 한다.

## Planner 결과를 QA가 활용하는 방식

PlannerAgent가 만든 결과는 직접 QA 점수 계산에 들어가지는 않지만, `pipeline_e2e.py`에서 Coder 입력으로 전달된다.

- task description
- acceptance criteria
- assumptions
- dependency tier

이 정보 덕분에 Coder는 어떤 파일을 수정해야 하는지, 어떤 동작이 요구되는지, 어떤 순서로 진행해야 하는지를 plan 기반으로 이해한다. QA는 그 결과물을 테스트와 리뷰로 검증한다.

## End-to-End Pipeline 설명

최종 흐름은 아래와 같다.

```text
Requirement
-> PlannerAgent.plan()
-> sample_plan.json
-> spec.md
-> tasks/task-001.md ...
-> CoderAgent
-> QAAgent.evaluate()
-> feedback
-> Coder retry
-> approve
```

## QA feedback loop 설명

1. iteration 1에서는 Coder가 일부러 불완전한 `divide()` 구현을 작성한다.
2. QA가 pytest, coverage, diff 리뷰를 실행한다.
3. 테스트 실패가 발생하면 `request_changes`를 반환한다.
4. iteration 2에서 Coder가 plan의 acceptance criteria와 QA feedback을 반영해 코드를 수정한다.
5. QA가 다시 실행되어 조건을 만족하면 `approve`를 반환한다.

이 구조 덕분에 planning 결과와 QA feedback이 모두 다음 수정 단계에 반영된다.

## tier DAG 설명

Week 08 PlannerAgent가 생성한 task dependency를 기반으로 tier가 계산된다.

- dependency 없음 -> tier 1
- dependency 있음 -> `max(dep tier) + 1`

현재 데모에서는 일반적으로 아래처럼 생성된다.

- `task-001 -> 1`
- `task-002 -> 2`
- `task-003 -> 3`

## 실행 방법

설치 명령:

```bash
python -m pip install pytest pytest-json-report pytest-cov
```

실행 명령:

```bash
python pipeline_e2e.py
```

검증 명령:

```bash
python -m pytest -q
```

## 생성 산출물

Planner 산출물:

- `sample_plan.json`
- `spec.md`
- `validation_report.json`
- `tasks/task-001.md`
- `tasks/task-002.md`
- `tasks/task-003.md`

QA 산출물:

- `qa_reports/iteration-01.json`
- `qa_reports/iteration-02.json`
- `qa_reports/pipeline-summary.json`
- `qa_reports/qa_history.json`

## coverage와 최종 판정 기준

- `approve`: 테스트 통과, coverage 70% 이상, 리뷰 block 없음
- `request_changes`: 테스트 실패/오류가 있거나 coverage가 70% 미만
- `reject`: 리뷰 결과가 `block`이거나 review score가 40 미만

## 제출 제외 대상

다음 임시 파일은 실행 중 생성될 수 있지만 제출 대상이 아니다.

- `__pycache__/`
- `.pytest_cache/`
- `.coverage`
- `coverage.json`
- `.report.json`
- `*.pyc`

