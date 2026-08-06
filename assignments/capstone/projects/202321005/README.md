# Socratic Tutor — 정답을 주지 않는 교육용 에이전트 시스템

초등학생 수준의 기본 문제(예: 덧셈·뺄셈 문장제)에서 학생의 답을 입력받아
**정답을 한 번도 알려주지 않으면서** 질문만으로 오개념을 교정하도록 유도하는
4-모듈 · 이중 루프 · 3-tier 방어 에이전틱 시스템. (예제 문제: `labs/math_01.json` — 버스 뺄셈)

> 제안서: [proposal.md](proposal.md) · 데이터 계약: [docs/artifacts.md](docs/artifacts.md)

## 구조

```
SOCRATES.md                  # 공유 헌법 (Zero-Answer · 힌트 Level) — 정답 0
.claude/agents/              # 역할별 시스템 프롬프트
  analysis.md  dialogue.md  qcritic.md  logging.md
docs/artifacts.md            # 8종 아티팩트 계약 + 불변식(INV-1~5)
labs/math_01.json            # 정답 뱅크 (정답 영역 원천) — 버스 뺄셈 문제
src/
  schemas.py                 # 단일 진실 원천 (pydantic v2) — 계약을 코드로 강제
  llm.py  prompts.py         # 주입 가능한 LLM 레이어 (Fake / Anthropic)
  validator.py               # Deterministic 센서 (순수 코드, .md 없음)
  modules/                   # Analysis / Dialogue / Review / Logging
  orchestrator.py            # SocraticTutor: 이중 루프 + 백프레셔 + CLI 데모
tests/                       # 33개 — Tier3 누출 / AND 게이트 / E2E
```

## Tier 3 방어 (이 프로젝트의 핵심)

"정답을 안 준다"를 **검증 가능한 명제**로 환원:

| 불변식 | 의미 | 강제 수단 |
|--------|------|----------|
| INV-1 | `reference_solution` 은 디스크에 안 씀 | lab dict 메모리 전용 + grep 테스트 |
| INV-2/3 | `forbidden_content` 가 Dialogue 데이터에 부재 | `DialogueGap` 에 필드 자체가 없음 (pydantic `extra="forbid"`) |
| INV-5 | `retry_hint` 도 정답 누출 금지 | Validator 이중 통과 |

→ 데이터(`artifacts.md`)와 프롬프트(`SOCRATES.md`/agents) **양쪽**에 정답이 없어야 닫힌다.

## 실행

```bash
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python -e ".[dev]"

.venv/bin/python -m src.orchestrator     # API 키 없이 결정적 데모 (백프레셔 시연)
.venv/bin/python -m pytest -q            # 전체 테스트
```

운영 시에는 `FakeClient` 자리에 `AnthropicClient` 를 주입한다 (`ANTHROPIC_API_KEY` 필요,
모델 라우팅 Opus/Sonnet/Haiku 는 `src/llm.py:MODEL_ROUTING`).
