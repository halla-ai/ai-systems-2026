# Docs-Code Drift Detector

README, docstring, API docs와 Python 소스 코드 간 **drift**(타입·파라미터·반환 구조·의미 불일치)를 탐지하고, 문서 patch 생성 → pytest QA → (선택) GitHub PR까지 수행하는 멀티에이전트 파이프라인입니다.

한 번의 `scan` 명령으로 전체 파이프라인이 실행됩니다.

| 구분 | 처리 방식 |
|------|-----------|
| **Structural drift** | 자동 탐지 → doc patch → QA loop (실패 시 Fix 재시도, 최대 5회) |
| **Semantic drift** | `--detect-semantic`으로 후보 탐지 → **patch 제외**, PR·gate에서 HITL |
| **코드 수정** | 자동 적용 안 함 (governance 추천 텍스트만) |
| **PR** | `--dry-run-pr` (미리보기) 또는 `--create-pr --hotl-approved` (실 PR, gh 필요) |

```bash
# 전체 파이프라인 (데모)
python -m docs_code_drift_detector scan testproject -o testproject/output --use-llm --detect-semantic --dry-run-pr

# 반복 가능성 검증 (동일 입력 3회)
python -m docs_code_drift_detector eval tests/fixtures/sample_project -o eval_out -n 3
```

---

## 수업 개념 적용 (Week 1–7)

| 주차 | 개념 | 적용 |
|------|------|------|
| Week 1 | AI 패러다임 전환 | `orchestrator.py` 멀티에이전트 파이프라인 |
| Week 1 | HOTL | `approval_gate.json` + `gate` CLI + PR merge 전 human 승인 |
| Week 2 | Governance-as-Code | `governance.py` — structural 자동 / semantic `human_review` |
| Week 3 | MCP | `mcp/` — filesystem, pytest, GitHub (dry-run · live) |
| Week 4 | Loop | Fix↔QA inner loop + HOTL↔QA outer loop (`pipeline_cycles.py`) |
| Week 5 | Context 관리 | 함수 단위 분석 (`_function_level_code_specs`) |
| Week 6 | Instruction tuning | `skills/*/SKILL.md` rubric + LLM doc/README 보조 |
| Week 7 | Multi-agent SDLC | Doc/Code/Drift/Fix/QA/PR + Reviewer + Hooks |

상세 아키텍처: [docs/architecture/L1-L7.md](docs/architecture/L1-L7.md)

---

## 구현 결과

### 파이프라인 (`scan` 한 번에 실행)

```
README / docstring / API docs  →  Doc Analyzer   →  doc_spec.json
Python source (AST)            →  Code Analyzer  →  code_spec.json
                                        ↓
                                 Drift Detector  →  drift_report.json
                                        ↓
                                   Governance    →  decisions
                                        ↓
                              Reviewer + Hooks  →  review_verdict.json
                                        ↓
                                 Fix Generator  →  patch.diff
                                        ↓
                    ┌──────── QA Loop (pytest, max 5) ────┐
                    │         ↑ pytest fail                 │
                    └──── Fix Generator 재호출 ─────────────┘
                                        ↓
                                   PR Agent       →  pr_dry_run.txt / GitHub PR
                                        ↓
                              Human Approval      →  approval_gate.json
                    ┌──────── QA만 재실행 (pending, max 5) ─┘
```

### CLI 명령

| 명령 | 역할 |
|------|------|
| `scan` | 전체 파이프라인 실행 |
| `replay` | `.events.jsonl` 타임라인·`replay_summary.json` |
| `gate` | `approval_gate.json` 상태 변경 (`approved` / `rejected` / `pending`) |
| `eval` | 동일 프로젝트 N회 실행 → `eval_summary.json` (반복 가능성) |
| `benchmark` | 30함수 labeled set → precision/recall/FPR (`benchmark_report.json`) |

`scan` 플래그: `--wait-hotl` (gate 승인까지 블로킹), `--wait-hotl-timeout` (초, 기본 300)

### 패키지 구성

| 모듈 | 역할 |
|------|------|
| `code_analyzer.py` | AST 기반 함수 시그니처·return 타입 추론 |
| `doc_analyzer.py` | README/docstring/API docs 파싱 |
| `drift_detector.py` | structural mismatch 탐지 |
| `llm_semantic_detector.py` | semantic 후보 탐지 (`--detect-semantic`) |
| `governance.py` | 테스트·typing·docstring 계약 기반 수정 방향 결정 |
| `fix_generator.py` | 문서 `patch.diff` 생성, 코드는 추천 텍스트만 |
| `qa_loop.py` | patch 적용 후 pytest 반복 |
| `pipeline_cycles.py` | Fix↔QA · HOTL↔QA 루프 |
| `pr_agent.py` | PR dry-run / `gh` 실 PR 생성 |
| `event_store.py` | `.events.jsonl` append-only 로그 |
| `cli.py` | `scan`, `replay`, `gate`, `eval` |

### 탐지 범위 (In Scope)

| 유형 | 예시 | patch |
|------|------|-------|
| `return_type_mismatch` | 문서 `dict` vs 코드 `list` | 자동 |
| `parameter_default_mismatch` | 문서 `loud=False` vs 코드 `loud=True` | 자동 |
| `parameter_type_mismatch` | 문서 `str` vs 코드 `int` | 자동 |
| `return_structure_mismatch` | 문서 `list[dict]` vs 코드 `dict` | 자동 |
| `semantic_mismatch` | doc 의미 vs 코드 동작 (`--detect-semantic`) | **HITL only** |

### 제외 범위 (Out of Scope)

- **Semantic 자동 patch** — 후보 탐지만, 문서/코드 자동 수정 없음
- **코드 자동 수정** — 동작 변경 위험으로 추천 텍스트만 제공
- **GitHub PR 리뷰 자동 폴링** — `--wait-hotl`은 `approval_gate.json` 폴링 (gh 리뷰 웹훅은 Post-MVP)

---

## 실행 예시

### 기본 스캔

프로젝트 루트에서 README와 소스를 비교합니다. 결과는 스캔 대상 폴더에 저장됩니다.

```bash
python -m docs_code_drift_detector scan .
```

### 출력 경로 지정

`drift_report.json`, `patch.diff`를 `./output` 폴더에 저장합니다.

```bash
python -m docs_code_drift_detector scan . -o ./output
```

### sample_project 스캔

테스트용 fixture 프로젝트를 스캔하는 예시입니다.

```bash
python -m docs_code_drift_detector scan tests/fixtures/sample_project -o tests/fixtures/scan_output
```

### testproject 데모 (structural + semantic + LLM)

의도적 drift 포함 데모: [testproject/DEMO.md](testproject/DEMO.md)

```bash
python -m docs_code_drift_detector scan testproject -o testproject/output --use-llm --detect-semantic --dry-run-pr
```

### PR dry-run 미리보기 (Week 1 HOTL)

스캔 후 PR title/body를 생성합니다. **`gh` 명령은 실행하지 않습니다.**

```bash
python -m docs_code_drift_detector scan tests/fixtures/sample_project -o tests/fixtures/scan_output --dry-run-pr
```

### Human 승인 플래그

```bash
python -m docs_code_drift_detector scan . --hotl-approved
```

생성 파일:
- `drift_report.json` — drift 목록 및 governance 결정
- `run_report.json` — 전체 run 요약 (L7)
- `.events.jsonl` — 이벤트 로그 (L4)
- `review_verdict.json` — Reviewer 판정 (L7)
- `patch.diff` — README/docstring 수정 제안
- `pr_dry_run.txt` — PR title/body dry-run 출력 (optional)

### 테스트 실행

drift detector **도구 자체**의 단위·통합 테스트를 실행합니다.

```bash
python -m pytest tests -v
```

---

## 출력 예시

`tests/fixtures/sample_project` 스캔 결과 (`functions_scanned: 3`, `drift_count: 4`):

### 터미널 출력

```
Scanned 3 functions.
Found 4 drift(s).
Report: tests/fixtures/scan_output/drift_report.json
Patch:  tests/fixtures/scan_output/patch.diff
```

### drift_report.json (발췌)

```json
{
  "project_root": ".../tests/fixtures/sample_project",
  "functions_scanned": 3,
  "drift_count": 4,
  "drifts": [
    {
      "function": "parse_json",
      "module": "api",
      "drift_type": "return_structure_mismatch",
      "doc_value": "dict: Parsed data",
      "code_value": "list",
      "confidence": 0.91,
      "evidence": {
        "doc": "returns dict: Parsed data",
        "code": "returns list"
      }
    },
    {
      "function": "greet",
      "module": "api",
      "drift_type": "parameter_default_mismatch",
      "doc_value": null,
      "code_value": "True",
      "evidence": {
        "doc": "loud=None",
        "code": "loud=True"
      }
    },
    {
      "function": "fetch_items",
      "module": "api",
      "drift_type": "return_structure_mismatch",
      "doc_value": "list[dict]: Item list",
      "code_value": "dict",
      "confidence": 0.91
    }
  ],
  "decisions": [
    {
      "function": "parse_json",
      "direction": "update_doc",
      "reason": "Tests exist; code is the source of truth."
    }
  ]
}
```

### patch.diff (발췌)

문서(docstring)만 수정 제안합니다. 코드는 변경하지 않습니다.

```diff
--- a/api.py
+++ b/api.py
@@ -4,4 +4,4 @@
     data (str): JSON string.

 Returns:
-    dict: Parsed data.
+    list
```

### PR dry-run 출력 (발췌)

```
============================================================
DRY-RUN PR PREVIEW (no gh command executed)
============================================================

TITLE
------------------------------------------------------------
docs: fix 4 documentation drift(s) in sample_project

BODY
------------------------------------------------------------
## Summary
- Functions scanned: **3**
- Drifts detected: **4**
...
============================================================
TODO: GitHub PR creation via gh CLI / GitHub API (not implemented)
============================================================
```

---

## MVP Evaluation

### 평가 대상 테스트셋

`tests/fixtures/sample_project` — 의도적 drift 3함수:

| 함수 | 의도된 drift | 탐지 여부 |
|------|-------------|----------|
| `parse_json` | README `dict` vs 코드 `list` | ✅ |
| `greet` | README `loud=False` vs 코드 `loud=True` | ✅ (default mismatch) |
| `fetch_items` | README `list[dict]` vs 코드 `dict` | ✅ |

### MVP 정량 결과 (sample_project 기준)

| 지표 | 결과 | 비고 |
|------|------|------|
| Functions scanned | 3 | `api.py` 공개 함수 |
| Drifts detected | 4 | docstring `Returns:` 설명 포함 시 false positive 2건 포함 |
| Core drift recall | 3/3 | 의도적 drift 전부 탐지 |
| False positive | 2 | `greet`, `parse_json` docstring `Returns: type: desc` 파싱 한계 |
| PR dry-run | ✅ | title/body 생성, gh 미실행 |
| Doc patch 생성 | ✅ | docstring 수정 diff 생성 |
| Code auto-fix | ❌ (by design) | 추천 텍스트만 (governance `suggest_code` 시) |

### 알려진 한계

1. **Docstring `Returns:` 파싱** — `int: Sum of a and b` 형태를 타입+설명으로 분리하지 못해 false positive 발생 가능
2. **README 우선순위** — docstring과 README가 동시에 있으면 docstring 계약이 우선 매칭될 수 있음
3. **Semantic drift** — structural만 자동 patch; semantic은 `--detect-semantic` + HITL (자동 수정 없음)

## Full Vision (LLM · CI · 실PR)

proposal 풀 비전이 opt-in으로 확장되었습니다.

| 기능 | 상태 | 사용법 |
|------|------|--------|
| LLM doc parsing | ✅ | `--use-llm` + `OPENAI_API_KEY` |
| LLM README rewrite | ✅ | `--use-llm` — Fix Generator가 README를 API로 갱신 (실패 시 regex fallback) |
| Semantic mismatch (HITL) | ✅ | `--detect-semantic` — LLM 의심 후보만, **자동 patch 제외**, PR에 HITL 표시 |
| QA Loop + patch 검증 | ✅ | patch temp 적용 후 pytest (최대 5회); 실패 시 Fix Generator **전체 재호출** |
| HOTL ↔ QA outer loop | ✅ | `approval_gate.json` pending 시 QA만 재실행 (`--max-hotl-cycles`, 기본 5) |
| GitHub PR (실제) | ✅ | `--create-pr --hotl-approved` + gh auth |
| GitHub Actions CI | ✅ | `.github/workflows/drift-detector.yml` |
| Docker | ✅ | `Dockerfile` |
| Semantic auto-patch | ❌ | `--detect-semantic`은 후보 탐지만, patch/merge는 HITL |
| 코드 자동 수정 | ❌ | 의도적 제외 |
| Event replay | ✅ | `python -m docs_code_drift_detector replay -o output` |
| Repeatability eval | ✅ | `python -m docs_code_drift_detector eval tests/fixtures/sample_project -o eval_out -n 3` |
| HOTL gate CLI | ✅ | `python -m docs_code_drift_detector gate -o output approved` |
| HOTL in-process wait | ✅ | `scan ... --wait-hotl` — gate 승인까지 같은 프로세스에서 대기 |

```bash
# LLM 보조 doc 파싱 (Week 6)
OPENAI_API_KEY=sk-... python -m docs_code_drift_detector scan . --use-llm --dry-run-pr

# 실제 PR 생성 (Week 1 HOTL — human 승인 필수)
python -m docs_code_drift_detector scan . --create-pr --hotl-approved
```

### Proposal §4 Benchmark (30 functions)

| 구성 | 내용 |
|------|------|
| Drift 함수 | 30 (type 10 + parameter 10 + structure 10) |
| Clean 함수 | 10 (false positive 측정) |
| Ground truth | `tests/fixtures/benchmark_ground_truth.json` |

```bash
python -m docs_code_drift_detector benchmark -o benchmark_out
# 또는
.\b.ps1
```

출력: `benchmark_out/benchmark_report.json`

**두 층으로 보고합니다 (중요):**

| 층 | 의미 | 발표에 쓸 것 |
|----|------|-------------|
| **Curated synthetic** (40 fn) | 탐지 규칙에 맞게 생성·튜닝된 합성 셋 → 점수가 **낙관적**일 수 있음 | “상한선 / 회귀 테스트” |
| **Realistic fixtures** (`sample_project`) | 손으로 라벨링, docstring 노이즈 포함 → **더 믿을 만한 수치** | **슬라이드 메인** |

예시 (`sample_project`): precision **0.75**, recall **1.0** (탐지 4건 중 의도적 drift 3건 + docstring FP 1건).

### Post-MVP

- [ ] LLM cost/latency 대시보드

---

## 요구 사항

- Python 3.12+ (3.11에서도 동작 확인)
- pytest 8.0+ (개발용)

```bash
pip install -e ".[dev]"
```
