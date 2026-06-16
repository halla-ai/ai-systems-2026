# 📑 TraceLedger: AI 협업 컨텍스트 자산화 엔진

> **"AI와 함께한 고군분투의 기록, 팀의 영구적인 지식 자산이 됩니다."**

TraceLedger는 개발자가 AI(GPT, Claude 등)와 협업하며 발생하는 **'삽질 이력(Trial & Error)'**과 **'기술적 의사결정 맥락(Why)'**을 자동으로 포착하여, 전문적인 **런북(Runbook)**과 **ADR(Architecture Decision Record)**로 변환하는 지능형 에이전트 시스템입니다.

---

## 1. 🚀 핵심 가치 (Value Proposition)

1.  **컨텍스트 유실 방지**: LLM 기반 코딩 시 발생하는 시행착오(Trial & Error)와 대안 검토 과정을 포착하여 지식의 블랙박스화를 방지합니다.
2.  **문서화 자동화 (Zero-Friction)**: 개발자가 번거로워하는 기술 문서(Runbook, ADR) 작성을 에이전트가 자동 수행하여 프로젝트 지식 베이스를 최신 상태로 유지합니다.
3.  **구현과 이해의 불일치 해소**: 작성자 본인조차 AI 생성 코드의 의도를 잊어버리는 현상을 방지하고, 유지보수성을 확보합니다.

---

## 2. 🏗 아키텍처 (Agent OS Runtime L1-L7)

본 프로젝트는 13주차 강의 요구사항을 준수하여 설계된 **엔지니어링급 에이전트 시스템**입니다.

-   **L1 (Tools)**: `read_raw_log`(로그 분석), `write_artifact`(문서 저장) 등 실질적 도구 연동.
-   **L2 (Provider)**: 토큰 사용량 실시간 추적 및 예산 기반 실행 통제.
-   **L3 (Collaboration)**: **Ralph Loop** 기반의 `Planner-Worker-Reviewer` 협업 체계.
-   **L4 (Event Store)**: `.events.jsonl`에 모든 사고 과정과 툴 호출 이력을 시퀀스로 저장 (Replay 가능).
-   **L5 (Skill)**: 마크다운 SSOT 기반의 전문 페르소나 정의.
-   **L6 (Harness)**: Budget Stop(토큰/턴 제한) 및 Error Handling 거버넌스.
-   **L7 (Schema)**: JSON Schema 기반의 엄격한 `Task Packet` 통신 규격.

---

## 3. 🔄 작동 원리 (The Ralph Loop)

TraceLedger는 에이전트 간의 **자기 성찰(Self-Correction)** 루프를 통해 품질을 보장합니다.

1.  **Planner (분석가)**: AI 로그를 분석하여 근본 원인(Root Cause)과 의사결정 맥락을 짚어냅니다.
2.  **Worker (작가)**: 분석 결과를 바탕으로 전문적인 마크다운 문서를 초안합니다.
3.  **Reviewer (검증관)**: 원본 로그와 대조하여 정확성을 검사하고, 미흡할 경우 **수정 제안(Suggestions)**과 함께 루프를 재가동합니다.

---

## 4. 💡 왜 TraceLedger인가? (Vs. Simple GPT Summary)

단순히 GPT에게 요약시키는 것과 TraceLedger 에이전트 시스템은 차원이 다릅니다.

-   **신뢰성 (Reliability)**: `Reviewer` 에이전트가 모든 문서를 원본 로그와 교차 검증하여 할루시네이션을 원천 차단합니다.
-   **일관성 (Consistency)**: L7 Task Packet 규격에 따라 모든 지식을 동일한 엔지니어링 포맷(ADR-XXX)으로 자산화합니다.
-   **통제성 (Governance)**: L2/L6 계층을 통해 토큰 비용과 실행 턴 수를 관리하여 조직의 운영 효율을 보장합니다.
-   **경제성 (FinOps & Optimization)**: 프롬프트 캐싱(Prompt Caching)과 노이즈 필터링 전략을 결합하여, 방대한 대화 로그 입력 시 발생하는 토큰 비용을 최소화하고 상용화 가능한 수준의 효율을 확보했습니다.
-   **자동화 (Automation)**: 단순 텍스트 생성을 넘어 L1 도구를 통해 실제 저장소에 문서를 자동 커밋하고 린팅합니다.

---

## 5. 🚀 향후 확장 계획 (Future Roadmap)

1.  **Prompt Genealogy**: 코드가 완성되기까지의 프롬프트 진화 과정을 추적하여 '최적의 프롬프트 템플릿'을 역추출합니다.
2.  **Cross-Session Synthesis**: 여러 개발자의 삽질 로그를 통합 분석하여 팀 전체의 'Redis 마스터 가이드' 등을 자동 생성합니다.
3.  **GitHub Action Integration**: PR 생성 시 자동으로 TraceLedger가 가동되어 분석 보고서를 댓글로 남기는 CI/CD 파이프라인 구축.
4.  **Knowledge Map**: 팀 내 지식 분포와 기술 부채를 시각화하여 지식 격차(Knowledge Gap)를 실시간 리포팅합니다.

---

## 6. 📂 파일 구조

-   `agents/`: L3 에이전트(Planner, Worker, Reviewer) 로직
-   `core/`: L4/L6 하네스 및 통제 엔진
-   `prompts/`: L5 에이전트 전문 스킬 정의
-   `schema/`: L7 태스크 패킷 규격
-   `logs/`: 분석 대상인 AI 대화 원본 로그
-   `docs/`: 생성된 최종 결과물 (Runbook, ADR)

---

## 7. 🚀 시작하기

### 환경 변수 설정
```bash
export OPENAI_API_KEY="your-key"
export OPENAI_BASE_URL="https://openrouter.ai/api/v1" # OpenRouter 사용 시
export LLM_MODEL="google/gemini-2.0-flash-001"
```

### 실행
```bash
python3 main.py
```

실행 후 브라우저에서 `index.html`을 열면 에이전트의 내부 사고 과정(Trace)을 실시간으로 확인할 수 있습니다.
