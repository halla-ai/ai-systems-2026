# 아티팩트 계약 (Artifact Contract) — Socratic Tutor

> 본 문서는 구현(코드)보다 **먼저** 확정되는 모듈 간 계약이다.
> 단일 진실 원천(Single Source of Truth)은 `src/schemas.py`의 **pydantic v2 모델**이며,
> 디스크의 모든 `*.json`은 그 모델의 직렬화 결과다. 본 문서는 그 모델이 따라야 할 규약을 정의한다.
>
> 관련: [proposal.md](../proposal.md) §2.5(아티팩트 핸드오프), §3.2(정답 접근 매트릭스), §6(성공 기준).

---

## 0. 설계 불변식 (Invariants) — 깨지면 프로젝트가 무너지는 규칙

| ID | 불변식 | 강제 수단 |
|----|--------|----------|
| **INV-1** | `reference_solution`(정답 원문)은 **디스크의 공유 아티팩트 디렉토리에 절대 기록되지 않는다**. Analysis 모듈의 프로세스 메모리(lab dict)에만 존재. | lab dict 는 `load_lab()` 로 읽히지만 `orchestrator._persist` 가 lab 을 디스크에 쓰지 않음 — 정답을 저장하는 코드 경로 자체가 없음. grep 테스트로 검증. |
| **INV-2** | 정답에서 파생된 문자열(`forbidden_content`)은 **Dialogue 모듈이 읽는 어떤 아티팩트에도 포함되지 않는다**. | `dialogue_gap.json` 스키마에 해당 필드가 **존재하지 않음**. Validator 전용 `validator_rules.json`으로 분리. |
| **INV-3** | Dialogue 모듈에 주입되는 컨텍스트 dict의 **키 집합**은 `DialogueGap` 모델의 필드로 폐쇄된다(closed set). 다른 키 양식 거부. 칸 추가 금지 | `tests/test_tier3_leakage.py`가 금지 키(`reference_solution`, `forbidden_content`, `full_student_answer`) 키가 없는지 확인, 금지 키 억지 주입했을때 거부되는지 확인 |
| **INV-4** | 모든 아티팩트는 `req_id`로 한 턴(turn)에 묶인다. `req_id = f"{lab_id}-t{turn:02d}"`. | pydantic 양식 검증 + Logging 상관관계 추적. |
| **INV-5** | Review의 `retry_hint`(질문 생성에서 거절된 이유 --> 정답 포함안하는지)도 Validator를 1회 더 통과해야 Dialogue로 반송된다 (이중 필터). | `review_report.json` 생성 파이프라인 내부 게이트. |
| **INV-6** | `event_log.jsonl`은 **append-only**(덮어쓰기·삭제 없음)이며, 정답 파생 문자열(`reference_solution`·`forbidden_content`)을 **값으로 담지 않는다**(결과 enum·카운트·`req_id` 참조만). 모든 루프 상태 전이는 정확히 1개 이벤트로 기록된다. | 쓰기 경로를 append 단일 함수(`orchestrator.emit_event`)로 한정. grep 테스트로 정답·forbidden 문자열 부재 검증. `metrics.json`·`PATH.md`는 이 로그의 **투영(projection)** 이다. |

> **INV-1·INV-2가 곧 Tier 3 "정보이론적 방어"의 조작적 정의다.** "정답을 안 준다"는 추상 원칙이 아니라
> "정답 파생 데이터가 특정 모델/파일에 **타입 레벨로 부재**하다"는 검증 가능한 명제로 환원된다.

> **closed-loop 대응 (채점 기준 Must-have).** 본 시스템은 닫힌 루프(closed loop)로 평가되며 4개 필수 요소를 갖춘다:
> **task packet** = `dialogue_gap.json`(1a), **single worker loop** = Orchestrator 내부 재생성 루프(라이프사이클 3),
> **deterministic gate** = Review의 Validator(결정적), **event log** = `event_log.jsonl`(7, 아래). event log가 없으면
> closed loop로 성립하지 않으므로 필수다. Should-have의 `replay snapshot`은 event log를 재생(replay)하여 동일 상태를
> 재구성하는 기능이며, event log가 그 선행조건이다. (LLM 판단인 Q-Critic은 deterministic gate가 아니라 Should-have의 reviewer/judge에 해당.)

---

## 1. 아티팩트 맵 (전체 9종)

```
[학생 제출]
   │ (0) submission
   ▼
╔══════════════ Analysis Module (The Truth Center) ══════════════╗
║  (T) lab dict       ◀── lab bank 로드 (메모리 전용, 디스크 X)   ║
║      reference_solution · misconception_taxonomy                ║
║  Judge → Planner                                                ║
╚══════╤══════════════════════════════════════╤══════════════════╝
       │ (1a) dialogue_gap.json                │ (1b) validator_rules.json
       │      [정답 0]                         │      [forbidden만]
       ▼                                       ▼
╔══════════════════════╗              ┌────────────────────┐
║  Dialogue (Tutor)    ║              │  (Validator 전용)  │
║  [정답 접근 ❌]      ║              │  Dialogue 접근 ❌  │
╚══════╤═══════════════╝              └─────────┬──────────┘
       │ (2) question_draft                     │
       ▼                                        │
╔══════════════ Review Module ═══════════════════╪══════════════╗
║  Q-Critic (Advisory) ∥ Validator (Deterministic)◀┘            ║
║                  └──── AND ────┘                              ║
╚══════╤═════════════════════════════════════════╤═════════════╝
       │ (3) review_report.json                   │ (4) approved_question
       │  ├ reject → Dialogue 재생성 (feedback)   │
       │  └ pass ──────────────────────────────────▶ [학생에게 전달]
       ▼
╔════ Orchestrator(append) ∥ Logging Module(Observer) ═══════════╗
║  (7) event_log.jsonl   ◀── 전 상태 전이를 append-only 로 기록    ║
║  (5) session_state.json   (6) PATH.md + metrics.json ◀── (7)의 투영 ║
╚══════════════════════════════════════════════════════════════════╝
```
> 모든 루프 전이(packet 생성 → draft → gate verdict → retry → approve/reject → reset → commit)는 Orchestrator가 `event_log.jsonl`(7)에 1줄씩 append 한다. Logging Module은 이 로그를 fold 하여 (5)(6)을 만든다 → event log가 단일 진실 원천(SSOT), 나머지는 투영.

| # | 아티팩트 | 생산자 | 소비자 | 디스크 | 정답 포함 | 수명 |
|---|---------|--------|--------|:------:|:--------:|------|
| 0 | `submission` | 학생/CLI | Analysis | ✅ 감사용 | 학생코드만 | 턴 |
| T | `lab dict` (raw) | Analysis(lab bank) | **Analysis 내부만** | ❌ **금지** | ✅ 정답 | 세션 |
| 1a | `dialogue_gap.json` | Analysis(Planner) | Dialogue | ✅ | ❌ | 턴 |
| 1b | `validator_rules.json` | Analysis(Planner) | Validator | ✅ | ⚠️ forbidden | 턴 |
| 2 | `question_draft` | Dialogue | Review | transient | ❌ | 재생성 시도 |
| 3 | `review_report.json` | Review | Dialogue·Orch | ✅ | ❌ | 재생성 시도 |
| 4 | `approved_question` | Review/Orch | 학생·Logging | ✅ | ❌ | 턴 |
| 5 | `session_state.json` | Orchestrator | Analysis(다음턴) | ✅ | ❌ 메타 | 세션 |
| 6 | `PATH.md`/`metrics.json` | Logging | 사람 | ✅ | ❌ 메타 | 세션 |
| 7 | `event_log.jsonl` | Orchestrator(`emit_event`) | Logging·replay·사람 (Dialogue ❌) | ✅ **append-only** | ❌ 메타 | 세션 |

---

## 2. 스키마 정의

표기: `?` = 선택 필드, `[]` = 리스트, `enum{...}` = 허용값. 모든 모델은 `extra="forbid"`(미정의 키 거부).

### (0) `submission` — 학생 입력
```jsonc
{
  "lab_id": "MATH-01",            // 문제 식별자 (lab bank 키)
  "turn": 4,                      // 이번 세션의 턴 번호 (1-base)
  "student_answer": "15 더하기 7은 22명이요!",  // 학생이 적은 답·풀이
  "student_message": "이거 맞아요?",  // 자연어, optional
  "submitted_at": "<ISO8601, 호출측 주입>"
}
```
- `req_id`는 여기서 `f"{lab_id}-t{turn:02d}"`로 파생 → 모든 하위 아티팩트에 전파(INV-4).

### (T) 정답 영역 = lab dict (⚠️ 메모리 전용, INV-1)
별도 pydantic 모델로 감싸지 않는다. `labs/<lab>.json` 을 `load_lab()` 으로 읽은 **raw dict** 그대로 Analysis 메모리에만 존재한다.
```jsonc
// labs/math_01.json (= lab dict)
{
  "lab_id": "MATH-01",
  "reference_solution": "15 - 7 = 8, 답은 8명",  // 정답 원문
  "answer_concepts": ["내리는 것은 줄어듦", "줄어들면 뺄셈", "15에서 7만큼 거꾸로"],
  "misconception_taxonomy": {        // 이 문제에서 가능한 오개념 카테고리
    "operation_confusion": "줄어드는 상황인데 덧셈을 함",
    "direction_unaware": "내리면 줄어든다는 것을 모름"
  },
  "forbidden_templates": ["8명", "15-7", "15 - 7"]  // 1b 생성용 시드
}
```
- **이 dict 를 디스크에 다시 쓰는 코드 경로가 없다**(`_persist` 가 lab 을 기록하지 않음). Analysis 내부에서만 소비.
- Analysis 가 여기서 안전한 조각만 증류 → `dialogue_gap`(라벨만) + `validator_rules`(forbidden). 정답 원문은 어디로도 안 나감.

### (1a) `dialogue_gap.json` — Analysis → Dialogue (정답 0)
```jsonc
{
  "req_id": "MATH-01-t04",
  "student_status": {
    "student_mistake": "줄어드는 상황인데 덧셈을 함",   // 관찰된 실수 유형만 (학생 답안 원문 X)
    "misconception": "operation_confusion",          // taxonomy 키 중 하나
    "iteration_count": 4,
    "last_hint_level": 2,                            // enum{0,1,2,3}, 0=최초턴
    "allowed_hint_level": 2                          // 이번 턴 상한 (자동 상향 결과)
  },
  "pedagogical_goal": "학생이 '내리는 것 = 줄어드는 것'을 깨닫고 뺄셈을 떠올리게 한다",
  "prior_turns_summary": "Turn1~3: 더하기/빼기 상황은 구분함. 거꾸로 세기에서 막힘."  // optional, 압축본
}
```
- **금지 필드(스키마에 부재)**: `reference_solution`, `correct_answer`, `full_student_answer`, `forbidden_content`. ← INV-2/INV-3 증거.
- `allowed_hint_level`은 `last_hint_level`과 `iteration_count`로 Planner가 계산(예: 같은 오개념 2턴 지속 → +1, 상한 3).

### (1b) `validator_rules.json` — Analysis → Validator 전용
```jsonc
{
  "req_id": "MATH-01-t04",
  "forbidden_content": ["8명", "15-7", "15 - 7"],  // 정답 숫자·식 문자열
  "forbidden_nl_patterns": ["정답은 팔", "8명이 남"],  // 정답을 흘리는 한국어 표현(§7)
  "forbidden_markers": []                            // 선택: 추가 차단 마커
}
```
- Dialogue는 이 파일 **경로에 접근 권한 자체를 부여받지 않는다**(파일시스템 권한 + 코드상 미주입).

### (2) `question_draft` — Dialogue → Review
```jsonc
{
  "req_id": "MATH-01-t04",
  "attempt": 1,                    // 재생성 시도 번호 (1..MAX_RETRY)
  "text": "버스에서 사람이 내리면 버스 안 사람 수는 많아질까요, 적어질까요?",
  "intended_hint_level": 1         // Dialogue가 의도한 수위 (Q-Critic가 검증)
}
```

### (3) `review_report.json` — Review → Dialogue(feedback)
```jsonc
{
  "req_id": "MATH-01-t04",
  "attempt": 1,
  "question_draft": "15에서 7을 빼면 8명이 남겠죠?",
  "advisory_verdict": {
    "source": "Q-Critic",
    "result": "pass",              // enum{pass, reject}
    "reasons": []
  },
  "deterministic_verdict": {
    "source": "Validator",
    "result": "reject",
    "matched_forbidden": ["8명", "15 - 7"]   // 매칭된 forbidden 항목 (reject 근거)
  },
  "final_verdict": "reject",       // = pass iff 둘 다 pass (AND)
  "retry_hint": "정답 숫자를 빼고, 늘어나는지 줄어드는지를 묻는 질문으로 재구성할 것",  // reject 시만, Validator 재통과(INV-5)
  "approved_question": null         // pass일 때만 question_draft 복사
}
```
- **AND 규칙**: `final_verdict == "pass"` ⟺ `advisory.result=="pass" AND deterministic.result=="pass"`.
- `retry_hint` 합성: Advisory 우선 + Deterministic 부속 merge. 생성 직후 Validator로 1회 재검사(INV-5) — 통과 못 하면 일반화된 안전 문구로 폴백.
- **시도별 보존**: `review_report.json`은 *마지막 시도*만 담는다(호환). 거절된 시도까지 포함한 전체 기록은 같은 턴 디렉토리의 **`review_attempt_NN.json`**(N=attempt)로 따로 보존한다 → 디스크가 `event_log.jsonl`/trace 와 일치하고, 사후 감사에서 "왜 1·2번이 거절됐나"를 파일로 추적 가능.

### (4) `approved_question` — 학생에게 전달
```jsonc
{
  "req_id": "MATH-01-t04",
  "text": "버스에서 사람이 내리면 버스 안 사람 수는 많아질까요, 적어질까요?",
  "hint_level": 1,
  "retries_used": 1                 // 이 질문까지 걸린 재생성 횟수 (metrics 연계)
}
```

### (5) `session_state.json` — 턴 간 누적 상태
```jsonc
{
  "lab_id": "MATH-01",
  "session_id": "s_2026...",        // 호출측 주입
  "turn": 4,
  "hint_level_history": [0, 1, 2, 1],       // 턴별 실제 전달 수위 → 진동(난제②) 감지
  "misconception_history": ["operation_confusion", "operation_confusion"],
  "resolved_concepts": ["direction_unaware"],  // 학생이 이해 완료한 개념 (재질문 방지, 난제②)
  "context_reset_count": 1,
  "prior_turns_summary": "...",             // Logging이 압축해 갱신, Analysis가 다음 턴 1a에 주입
  "aha_moment_turn": null                    // 도달 시 턴 번호 기록
}
```
- 제안서 §2.5.1에서 `student_gap` 안에 섞여 있던 누적 상태(`iteration_count` 등)를 여기로 분리.
  gap(1a)은 **매 턴 새로 생성**, session_state는 **세션 내내 누적**이라 수명이 달라 분리 필수.

### (6) `metrics.json` — 정량 지표 (PATH.md는 사람용 마크다운)
```jsonc
{
  "session_id": "s_2026...",
  "lab_id": "MATH-01",
  "total_turns": 9,
  "review_retry_total": 11,
  "review_retry_avg": 1.2,           // §6 목표 ≤1.3
  "tier3_leak_count": 0,             // §6 절대 기준 = 0
  "validator_reject_count": 0,
  "qcritic_reject_count": 12,
  "context_reset_count": 1,
  "aha_reached": true,
  "hint_level_max": 2,
  "tokens": {"analysis": 0, "dialogue": 0, "review": 0, "logging": 0},
  "cost_usd": 0.0                    // §6 목표 ≤$0.80
}
```
- (6)은 (7) `event_log.jsonl`을 fold 한 **투영**이다. 동일 event log → 동일 metrics(결정적).

### (7) `event_log.jsonl` — append-only 이벤트 스트림 (closed-loop 척추, INV-6)
형식: **JSON Lines** (1 이벤트 = 1줄). Orchestrator가 모든 루프 상태 전이마다 정확히 1줄을 **추가만** 한다(덮어쓰기·삭제 없음). 정답·forbidden 문자열은 **값으로 담지 않고** 결과 enum·카운트·`req_id` 참조만 기록(INV-6) → Tier 3 유지. 이 로그가 단일 진실 원천이며 (5)(6)과 replay snapshot이 모두 여기서 파생된다.
```jsonc
// 공통 필드: seq(단조 증가 정수, append 순서=replay 순서) · ts(ISO8601, 호출측 주입) · req_id(INV-4) · event(enum) · data(이벤트별 메타)
{"seq":1,"ts":"2026-...","req_id":"MATH-01-t04","turn":4,"event":"turn_started","data":{}}
{"seq":2,"ts":"...","req_id":"MATH-01-t04","event":"packet_created","data":{"artifact":"dialogue_gap.json","allowed_hint_level":2}}        // task packet 발행
{"seq":3,"ts":"...","req_id":"MATH-01-t04","event":"draft_generated","data":{"attempt":1,"intended_hint_level":1}}                        // worker 출력
{"seq":4,"ts":"...","req_id":"MATH-01-t04","event":"gate_evaluated","data":{"attempt":1,"advisory":"pass","deterministic":"reject","final":"reject","matched_forbidden_count":2}}  // 결정적 게이트 판정(문자열 X, 카운트만)
{"seq":5,"ts":"...","req_id":"MATH-01-t04","event":"retry_triggered","data":{"from_attempt":1,"to_attempt":2}}                            // Backpressure
{"seq":6,"ts":"...","req_id":"MATH-01-t04","event":"question_approved","data":{"attempt":2,"hint_level":1,"retries_used":1}}
{"seq":7,"ts":"...","req_id":"MATH-01-t04","event":"context_reset","data":{"kind":"retry_exhausted"}}                                      // 발생 시만. kind∈{retry_exhausted, periodic}
{"seq":8,"ts":"...","req_id":"MATH-01-t04","event":"turn_committed","data":{"aha":false}}                                                 // session_state 영속화 직후
{"seq":9,"ts":"...","req_id":"MATH-01-t04","event":"judge_aborted","data":{"reason":"answer_copied"}}                                     // Judge가 정답 베낌 감지해 중단 시
```
- **`event` enum**: `turn_started · packet_created · draft_generated · gate_evaluated · retry_triggered · question_approved · context_reset · judge_aborted · turn_committed · session_ended`.
- **결정성·replay**: 같은 입력 + 같은 `FakeClient` → 같은 `(seq, event)` 시퀀스. replay snapshot(Should)은 이 파일을 seq 순으로 재생해 `session_state`·`metrics`를 재구성하는 것으로 정의된다.
- **Tier 3 (INV-6)**: `data`에 `reference_solution`·`forbidden_content` 원문 금지. reject 근거 상세가 필요하면 `(req_id, attempt)`로 `review_report.json`(3)을 참조한다(임베드 X).

```
1. CLI → submission(0) 구성, req_id = lab_id + turn
2. Analysis:
     a. lab dict(T) 메모리 로드 (load_lab, lab bank)
     b. Judge: student_answer가 reference_solution 베낌인지 판정 → 베낌이면 abort
     c. Planner: gap 계산 → dialogue_gap(1a) + validator_rules(1b) 두 파일로 분리 기록
3. 내부 루프 (attempt = 1..MAX_RETRY=3):
     a. Dialogue.generate(1a, feedback=직전 retry_hint) → question_draft(2)
     b. Review: Q-Critic(1a 기준) ∥ Validator(1b 기준) 병렬 → review_report(3)
     c. final_verdict == pass → approved_question(4), break
        else → feedback = retry_hint, continue
     d. attempt 초과 → Context Reset 트리거, session_state.context_reset_count++
4. approved_question(4) → 학생 전달
5. Logging: session_state(5) 갱신, metrics(6) 누적, 세션 종료 시 PATH.md 생성
```
> **이벤트 기록(7)은 위 흐름과 병행한다.** 2c·3a·3b·3c·3d·4·세션종료 각 전이 직후 Orchestrator가 `emit_event`로 `event_log.jsonl`에 1줄 append(append-only, INV-6). (5)(6)은 이 로그의 투영으로 만들어진다.

---

## 3.5 컨텍스트 리셋 & 연속성 정책

긴 세션에서는 LLM 대화 컨텍스트가 쌓이며 품질이 떨어진다(컨텍스트 랏). 이를 막기 위해
**대화 컨텍스트는 주기적으로 비우되, 학습 이력은 잃지 않는다.** 핵심은 휘발성 컨텍스트와
영속 상태를 분리하는 것이다.

### 두 종류의 "리셋" (혼동 주의)

| | **재생성 한도 초과 리셋** | **주기적 컨텍스트 리셋** |
|--|--------------------------|--------------------------|
| 트리거 | 한 질문 내부 루프가 `MAX_RETRY=3` 초과 | N턴 경과 **또는** 누적 토큰이 임계 초과 |
| 범위 | 그 질문 한 번 (안전 폴백으로 탈출) | 세션의 LLM 대화 컨텍스트 전체 |
| 기록 | `context_reset_count++` | `context_reset_count++` |
| 목적 | 못 푸는 질문에서 빠져나오기 | 컨텍스트 랏 누적을 끊기 |

> 라이프사이클 3-d의 Context Reset은 **전자**(비상 탈출)다. 후자(위생 관리)는 외부 루프 레벨 정책으로, 아래 절차를 따른다.

### 연속성 메커니즘 — 무엇이 살아남나

리셋은 **휘발성 대화 컨텍스트**(누적된 프롬프트/응답)만 버린다. 다음은 디스크에 영속되어 **그대로 살아남는다**:

- `session_state.json`(5) — 턴마다 `run_dir` 루트에 덮어쓰기 저장. 학습 이력의 단일 원천.
  - `prior_turns_summary` — Logging이 압축·갱신하는 지금까지의 요약
  - `resolved_concepts` / `misconception_history` — 이해 완료/잔여 오개념
  - `hint_level_history`, `aha_moment_turn`, `context_reset_count`

### 리셋 후 복원 절차

1. LLM 대화 컨텍스트를 비운다.
2. **지침 재주입**: `SOCRATES.md`(공유 헌법) + 역할별 시스템 프롬프트(`.claude/agents/*.md`)를 처음부터 다시 로드.
3. **상태 복원**: `session_state.json`을 읽어 `prior_turns_summary`·`resolved_concepts` 등을 다음 턴 `dialogue_gap`(1a)에 주입.
4. 다음 턴부터 이어서 진행. 학생 입장에선 이력이 보존된 채 대화가 계속된다.

**Tier 3 보장 유지**: 복원 시에도 정답(truth)은 절대 주입되지 않는다 — `session_state.json`은 메타 정보만 담으며(정답 미포함, INV-1), 재주입되는 지침 `.md`에도 정답 단서가 없다(D-5).

---

## 4. 검증 전략 (다음 단계 `tests/`에서 구현)

| 테스트 | 대상 불변식 | 방법 (무엇을 어떻게 확인하나) |
|--------|------------|------|
| `test_tier3_leakage.py` | INV-2/3 | Dialogue가 받는 데이터에 정답 관련 항목이 섞여 들지 않는지 본다. ① `DialogueGap` 모델이 가진 필드 목록을 꺼내, 금지 키(`reference_solution`, `forbidden_content`, `full_student_answer`)가 하나도 없는지 확인한다. ② 일부러 그 금지 키를 끼워 넣은 데이터를 Dialogue에 주입해 보고, 모델이 이를 거부하는지 확인한다. |
| `test_truth_never_persisted.py` | INV-1 | 정답이 파일로 새어 나가지 않았는지 본다. 공유 아티팩트 디렉토리의 모든 파일을 텍스트로 훑어(`grep`) `reference_solution`이라는 글자가 단 한 번도 등장하지 않음을 확인한다. (정답은 메모리에만 있어야 하고 디스크에는 없어야 함) |
| `test_and_gate.py` | AND 규칙 | 두 검사(Advisory·Deterministic)가 **둘 다 통과해야만** 통과시키는지 진리표로 확인한다. (통과, 통과)면 최종 통과, 나머지 세 조합(통과·실패 / 실패·통과 / 실패·실패)은 모두 거부되는지 본다. |
| `test_req_id_propagation.py` | INV-4 | 한 번의 대화 턴에서 생성된 모든 아티팩트가 **같은 `req_id`** 를 달고 있는지 확인한다. (같은 턴의 결과물끼리 ID가 일치해야 추적이 가능) |
| `test_retry_hint_validated.py` | INV-5 | 재시도 안내문(`retry_hint`)에 정답 단서(`forbidden_content`)가 들어 있지 않은지 확인한다. (거절 사유를 알려줄 때조차 정답이 흘러나가면 안 됨) |
| `test_schema_roundtrip.py` | 전체 | 스키마가 정상 동작하는지 본다. 각 모델을 JSON으로 저장(dump)했다가 다시 읽어(load) 원래 값과 같은지(왕복 일치) 확인하고, 정의에 없는 필드를 넣었을 때 `extra="forbid"` 규칙이 이를 거부하는지 확인한다. |
| `test_event_log.py` | INV-6 | event log가 닫힌 루프의 기록으로 성립하는지 본다. ① 한 턴 실행 후 `event_log.jsonl`의 `seq`가 1부터 빈틈없이 증가하는지(append 순서 보존), ② 각 줄에 `reference_solution`·`forbidden_content` 원문이 단 하나도 없는지(grep), ③ event log를 seq 순으로 replay 했을 때 재구성한 `metrics`가 실제 `metrics.json`과 일치하는지(투영=결정적 replay) 확인한다. |

---

## 5. 확정 사항 (결정 로그)

- **D-1**: `student_gap.json`을 `dialogue_gap.json`(정답0) + `validator_rules.json`(forbidden)으로 **분리**. 이유: 단일 파일이면 forbidden_content가 Dialogue 컨텍스트에 들어가 Tier 3 위반(INV-2).
- **D-2**: 단일 진실 원천 = **pydantic v2 모델**(`src/schemas.py`). 모든 JSON은 직렬화 결과.
- **D-3**: 누적 상태를 `session_state.json`으로 gap에서 분리(수명 차이).
- **D-4**: 정답 영역을 별도 `TruthContext` pydantic 모델로 감싸지 **않고**, `labs/<lab>.json` 을 `load_lab()` 으로 읽은 **raw dict** 로 Analysis 메모리에서만 다룬다. (모델 래퍼는 기능상 불필요 — INV-1 은 `_persist` 가 lab 을 기록하지 않는 것으로 보장되고 grep 테스트로 검증되므로, 래퍼 없이도 동일하게 안전. 단순화 우선.)
- **D-6**: `session_state.json`을 **턴마다 `run_dir` 루트에 영속화**(`orchestrator.persist_state`). `PATH.md`(사람용 전체 기록)·`metrics.json`(지표)과 별개로, 기계가 읽는 **연속성 상태**로 둔다. 이유: 컨텍스트 리셋(§3.5) 후 학습 이력을 복원하려면 디스크에 최신 상태가 남아 있어야 함. 정답 미포함이라 Tier 3 영향 없음.
- **D-7**: closed-loop Must-have인 **event log**를 `event_log.jsonl`(7, append-only JSON Lines)로 신설. 기존 `session_state.json`(턴마다 덮어쓰기)·`metrics.json`(집계)과 수명·성격이 달라 별도 아티팩트로 분리. **event_log를 단일 진실 원천(SSOT)으로 두고 (5)(6)·replay를 그 투영으로 정의** → 닫힌 루프 성립 + replay snapshot(Should) 선행조건 확보. 정답·forbidden 원문은 값으로 안 담음(INV-6, Tier 3 유지). 쓰기는 `orchestrator.emit_event` 단일 append 경로로 한정.
- **D-5**: 지침 파일을 단일 `SOCRATES.md`가 아니라 **공유 헌법(`SOCRATES.md`) + 역할별 시스템 프롬프트(`.claude/agents/{analysis,dialogue,qcritic,logging}.md`)**로 분리. 이유: ① 모듈별 모델·역할 상이, ② Week 9 QA 독립성(Q-Critic ≠ Dialogue 프롬프트), ③ Tier 3 — Dialogue 프롬프트에 정답 단서 부재(데이터 INV-2와 동일 논리). **Validator는 결정적 코드이므로 `.md` 없음.**
