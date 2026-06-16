# 14주차 캡스톤 프로젝트 중간 진행 보고서 (progress-week14.md)

**프로젝트 명칭**: TraceLedger (AI 협업 컨텍스트 자산화 및 자동 런북 생성 시스템)
**팀명**: trace-ledger
**학번 / 이름**: 202321006 / 김준서

---

## 1. Problem (문제 정의)

현재 개발자들이 LLM(GPT, Claude 등)을 활용해 코딩할 때, 소스 코드를 끊임없이 수정하고 반복(Trial & Error)하는 과정에서 발생하는 핵심 맥락(Context)과 디버깅 삽질 이력이 전부 유실된다. 최종 결과물인 코드만 Git에 남을 뿐, "AI가 왜 이 라이브러리를 포기하고 다른 대안을 택했는지", "어떤 프롬프트 루프를 거쳐 이 버그를 고쳤는지"에 대한 지식(Knowledge)은 블랙박스화된다. 

이는 결과적으로 개발자 본인조차 코드의 설계 의도를 파악하지 못하게 만들어 유지보수성을 극도로 떨어뜨리며, 기술 부채를 급격하게 가중시킨다. **TraceLedger**는 이러한 '구현과 이해의 불일치'를 해결하기 위해, 유실되는 대화 컨텍스트를 구조화된 문서(Runbook, ADR)로 영속화하는 에이전트 시스템이다.

---

## 2. Implementation Progress (Agent OS Runtime L1-L7)

13주차 강의 요구사항에 따라 다음과 같이 5개 이상의 계층을 명시적으로 구현했습니다.

### 2.1 계층별 구현 현황 (L1-L7 Full Stack)
- **L1 (Tool):** `read_raw_log`, `write_artifact` 실제 도구 구현 및 연동 완료.
- **L2 (Provider):** 토큰 사용량 실시간 추적 및 `total_tokens` 로깅 시스템 구축.
- **L3 (Collaboration):** **피드백 기반 Ralph Loop** 구현. Reviewer의 수정 제안(`suggestions`)을 다음 턴의 Planner/Worker에게 주입하여 자기 성찰(Self-Correction) 달성.
- **L4 (Event Store):** 모든 에이전트 이벤트 및 툴 호출 이력을 `.events.jsonl`에 타임스탬프와 함께 적재.
- **L5 (Skill):** Planner, Worker, Reviewer 역할을 마크다운 SSOT로 정의하여 페르소나 고정.
- **L6 (Harness):** **Budget Stop Mechanism** 도입. 정의된 토큰/턴 예산 초과 시 즉시 루프 차단 및 에스컬레이션.
- **L7 (Schema):** `jsonschema`를 이용한 **Task Packet 유효성 검증** 엔진 탑재. 규격에 맞지 않는 태스크는 실행 전 사전 차단.


---

## 3. Evidence of Execution (MVP 1단계)

### 3.1 Task Packet 기반 실행 로그
```bash
🚀 Executing Task: trace-ledger-2026-001
[Harness] task_started: {...}
[Planner] analysis_done: {"msg": "Root cause identified: Redis timeout..."}
[Worker] doc_created: {"file": "docs/runbooks/redis_fix.md"}
[Reviewer] verdict: {"status": "APPROVED"}
✅ TraceLedger task completed successfully.
```

### 3.2 .events.jsonl Replay Snapshot
에이전트가 삽질한 모든 과정을 재현할 수 있도록 타임스탬프와 함께 모든 툴 이벤트를 기록합니다.

---

## 4. Risk & Scope Management

- **Must have**: Task Packet 엔진, 턴/토큰 제한 하네스, 마크다운 런북 자동 생성 루프.
- **Scope Cut**: 실시간 IDE 확장 프로그램 및 배포 자동화 제외 (에이전트 핵심 논리에 집중).

---

## 5. 최종 발표 전략

1. **문제의식**: AI 코딩 과정에서 유실되는 귀중한 '디버깅 및 설계 맥락' 문제를 제기.
2. **해결책 시연**: TraceLedger를 통한 '삽질의 자산화(Runbook, ADR 생성)' 실시간 시연.
3. **기술적 차별화 (방어 논리 & FinOps)**: 
   - 단순한 GPT 프롬프팅이 아닌, L1-L7 아키텍처와 Ralph Loop(자기 성찰 루프)를 통해 결과물의 신뢰성과 일관성을 담보.
   - **비용 최적화(Cost Optimization)**: 대용량 로그 입력 시 발생하는 토큰 폭주를 막기 위해 L6 Harness의 Budget 통제 외에도 프롬프트 캐싱(Prompt Caching)과 노이즈 필터링 전략을 도입하여 상용 서비스 수준의 경제성 증명.
4. **비전 제시**: 향후 '프롬프트 계보 추적' 및 '다중 세션 지식 통합'으로 확장되는 팀 단위 지능 파이프라인 로드맵 제시.
