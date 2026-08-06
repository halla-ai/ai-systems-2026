# Lab 07 멀티에이전트 파이프라인

이 디렉터리는 Lab 07 과제 제출을 위한 코드와 문서를 포함합니다. 멀티에이전트 시스템의 설계 원칙을 적용하여 Planner→Coder 2단계 파이프라인을 구현하고, 나머지 단계의 설계를 문서화했습니다.

## 구성 파일

- `schemas/` — 에이전트 간 통신을 위한 JSON 스키마 정의입니다. 각 v1 스키마는 Agent OS Contracts에 기반해 최소 요구 사항을 만족하도록 작성했습니다.
- `base_agent.py` — 모든 에이전트가 상속하는 공통 기반 클래스로, 스키마 검증과 LLM 호출 로직을 캡슐화합니다.
- `planner_agent.py` — 사용자 요청을 서브태스크로 분해하여 계획을 생성하는 플래너 에이전트의 구현입니다.
- `coder_agent.py` — 플래너가 생성한 계획을 입력받아 코드를 수정하고 테스트를 실행하는 코더 에이전트의 구현입니다.
- `pipeline.py` — Planner와 Coder를 연결하여 간단한 2단계 파이프라인을 실행하는 스크립트입니다.
- `pipeline_design.md` — Researcher, QA, Reviewer를 포함한 5단계 전체 파이프라인의 설계 문서입니다.
- `sessions/example/.events.jsonl` — 예시 실행 로그를 담은 JSONL 파일입니다.
- `replay_snapshot.json` — 실행 로그를 통해 재현한 최종 상태를 요약한 스냅샷입니다.

## 실행 방법

1. Python 환경에서 필요한 패키지를 설치합니다. 예를 들어 JSON 스키마 검증을 위해 `jsonschema`가 필요합니다.

   ```bash
   pip install jsonschema
   ```

2. 루트 디렉터리에서 `pipeline.py`를 실행하여 Planner와 Coder를 순차적으로 실행할 수 있습니다.

   ```bash
   python pipeline.py
   ```

   실행 중에 목표(Objective)와 선택적으로 코드베이스 요약을 입력하면 플래너가 계획을 생성하고, 코더가 계획에 따라 코드를 수정한 뒤 결과를 출력합니다.

3. 환경 변수 `AI_CLI`를 설정하면 외부 AI 코딩 도구를 변경할 수 있습니다.

   ```bash
   export AI_CLI=gemini
   ```

## 주의 사항

- 이 코드는 예제용이므로 테스트 스위트와 실제 코드베이스가 없을 경우 `CoderAgent`가 수행하는 코드 변경은 발생하지 않습니다. 실제 환경에서는 `changes` 리스트를 git diff 결과로 채워야 합니다.
- 제공한 JSON 스키마는 과제의 최소 요건을 충족하도록 설계되었으며, 실제 응용에 맞게 확장할 수 있습니다.
- 파일과 디렉터리 이름은 모두 영문으로 작성하여 macOS NFD 분해 문제를 방지했습니다.
