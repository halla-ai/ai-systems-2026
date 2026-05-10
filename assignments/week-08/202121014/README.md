# Week 08: Planner Agent

## Week 08 목표 설명

이 과제의 목표는 모호한 요구사항을 분석해서 구현 전에 사용할 planning artifact를 만드는 것이다.  
`PlannerAgent`는 코드베이스를 읽고, 요구사항을 구조화하고, `spec.md`, `sample_plan.json`, `validation_report.json`, `tasks/*.md`를 생성한다.

## PlannerAgent 역할

`planner_agent.py`의 `PlannerAgent`는 다음 작업을 담당한다.

- 코드베이스의 Python 파일 분석
- 파일/패키지 구조 요약
- 함수/클래스/import 정보 추출
- 요구사항 기반 task list 생성
- spec markdown 생성
- spec 품질 검증
- dependency DAG 기반 TASK 문서 생성

## spec -> architect 분리 개념

Planner는 "무엇을 해야 하는가"를 정리한다.  
Architect 또는 이후 단계 에이전트는 "어떻게 구현할 것인가"를 구체화한다.  
이 과제는 구현 자체보다, 구현 전에 사용할 명확한 작업 명세와 DAG를 만드는 데 초점을 둔다.

## Context Rot과 코드베이스 요약 전략

긴 작업에서는 초기에 읽은 코드 문맥이 흐려질 수 있다. 이를 줄이기 위해 PlannerAgent는 전체 코드를 그대로 복사하지 않고 다음 정보만 요약한다.

- Python 파일 목록
- 디렉터리 구조
- 함수 시그니처
- 클래스 이름
- import 정보

이 요약은 이후 단계가 필요한 문맥만 빠르게 재구성하도록 돕는다.

## analyze_codebase 설명

`analyze_codebase()`는 `pathlib.Path.rglob("*.py")`로 Python 파일을 찾고 다음 정보를 반환한다.

- 전체 Python 파일 수
- 상대 경로 목록
- 디렉터리 구조
- import 집합
- 파일별 함수/클래스 분석 결과

특히 `calculator.py`를 실제 planning 대상 코드로 분석한다.

## validate_spec 설명

`validate_spec()`는 생성된 plan이 최소 품질 기준을 만족하는지 자동 검사한다.

검사 항목:

- `acceptance_criteria` 존재 여부
- 각 task의 `acceptance_criteria`가 2개 이상인지
- `assumptions` 존재 여부
- `out_of_scope` 존재 여부

결과는 `validation_report.json`에 저장된다.

## dependency DAG 설명

`create_task_dag()`는 task dependency를 바탕으로 tier를 계산한다.

- dependency가 없으면 tier 1
- dependency가 있으면 `max(dep tier) + 1`

이 결과는 `tasks/task-001.md` 같은 파일의 front matter에 기록된다.

## 실행 방법

```bash
python planner_agent.py
```

실행 시 다음 산출물이 생성 또는 갱신된다.

- `sample_plan.json`
- `spec.md`
- `validation_report.json`
- `tasks/task-001.md`
- `tasks/task-002.md`
- `tasks/task-003.md`

## 실제 생성된 spec.md 설명

`spec.md`는 planner가 생성한 Markdown 명세서다.  
프로젝트 개요, task 목록, acceptance criteria, assumptions, out_of_scope를 포함한다.  
즉, 다음 단계 에이전트가 구현 전에 읽어야 할 핵심 요구사항 요약본이다.

## TASK DAG tier 설명

이 과제의 데모 DAG는 순차 구조다.

- `task-001`: 현재 동작 분석
- `task-002`: 구현-ready spec 정리
- `task-003`: 실행 순서와 검증 계획 정의

따라서 tier는 보통 `task-001 -> 1`, `task-002 -> 2`, `task-003 -> 3`으로 생성된다.

