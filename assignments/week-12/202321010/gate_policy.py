"""
gate_policy.py
--------------
다단계 게이트 정책 – LLM Judge 를 직접 pass/fail 로 사용하지 않고
결정론적 검사와 결합하는 이유를 구현으로 보여줌.

정책 설계 근거
─────────────
1. 비결정론성(non-determinism)
   같은 코드에 대해 LLM 실행마다 점수가 달라질 수 있어
   단독 pass/fail 게이트로 사용하면 재현성을 보장할 수 없음.

2. 편향(bias)
   길이 편향 등으로 인해 짧지만 올바른 코드가 거부될 수 있음.
   (Sample 6: 인간 8점 → LLM 6.4점 → 직접 게이트면 FAIL)

3. 보안 사각지대
   LLM 은 SQL 인젝션·하드코딩 자격증명을 탐지하더라도
   패턴 기반 결정론적 검사보다 신뢰성이 낮음.

4. 가변성(variability)
   동일 코드라도 프롬프트 버전, 온도, API 모델 버전에 따라 점수 변동.

5. 조작 가능성(gameable)
   장황한 주석·긴 코드 작성만으로 높은 점수를 유도할 수 있음.

게이트 정책 3단계
─────────────────
Tier 1 (Hard Gate – 결정론적)
  문법 오류 OR 보안 점수 < 4.0 → 즉시 BLOCKED (LLM 점수 무시)

Tier 2 (Soft Gate – LLM 보조)
  Tier 1 통과 시, LLM overall < 4.5 → REVIEW_REQUIRED

Tier 3 (Composite Score)
  가중합 = det_overall * 0.60 + llm_overall * 0.40
  >= 7.0 → PASS
  >= 5.0 → CONDITIONAL_PASS (사람 리뷰 권장)
  <  5.0 → FAIL
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


# ─────────────────────────────────────────────────────────────────────────────
# 게이트 결과 열거형
# ─────────────────────────────────────────────────────────────────────────────

class GateOutcome(str, Enum):
    PASS             = "PASS"
    CONDITIONAL_PASS = "CONDITIONAL_PASS"
    REVIEW_REQUIRED  = "REVIEW_REQUIRED"
    FAIL             = "FAIL"
    BLOCKED          = "BLOCKED"

    def emoji(self) -> str:
        return {
            "PASS":             "PASS",
            "CONDITIONAL_PASS": "COND",
            "REVIEW_REQUIRED":  "REVW",
            "FAIL":             "FAIL",
            "BLOCKED":          "BLKD",
        }[self.value]


@dataclass
class GateDecision:
    sample_id:      int
    outcome:        GateOutcome
    triggered_tier: int         # 1, 2, or 3
    det_overall:    float
    llm_overall:    float
    composite:      float
    reason:         str


# ─────────────────────────────────────────────────────────────────────────────
# 정책 상수
# ─────────────────────────────────────────────────────────────────────────────

TIER1_SYNTAX_REQUIRED   = True   # 문법 오류 시 즉시 차단
TIER1_SEC_MIN           = 5.0    # 보안 점수 최소치 (SQL 인젝션·자격증명 노출 차단)
TIER2_LLM_MIN           = 4.5    # LLM judge 최소치 (소프트)
TIER3_PASS_THRESHOLD    = 7.0    # 합성 점수 PASS 기준
TIER3_COND_THRESHOLD    = 5.0    # 합성 점수 CONDITIONAL_PASS 기준
COMPOSITE_DET_WEIGHT    = 0.60   # 결정론적 가중치
COMPOSITE_LLM_WEIGHT    = 0.40   # LLM 가중치


# ─────────────────────────────────────────────────────────────────────────────
# 게이트 평가 함수
# ─────────────────────────────────────────────────────────────────────────────

def evaluate_gate(
    sample_id:    int,
    syntax_ok:    bool,
    det_security: float,
    det_overall:  float,
    llm_overall:  float,
) -> GateDecision:
    """
    3단계 정책을 적용하고 GateDecision 반환.

    Parameters
    ----------
    syntax_ok     : 결정론적 평가의 문법 검사 결과
    det_security  : 결정론적 보안 점수 (0-10)
    det_overall   : 결정론적 종합 점수 (0-10)
    llm_overall   : LLM Judge 종합 점수 (0-10)
    """
    composite = round(
        COMPOSITE_DET_WEIGHT * det_overall + COMPOSITE_LLM_WEIGHT * llm_overall, 2
    )

    # ── Tier 1: Hard Gate ──────────────────────────────────────────────────
    if TIER1_SYNTAX_REQUIRED and not syntax_ok:
        return GateDecision(
            sample_id=sample_id,
            outcome=GateOutcome.BLOCKED,
            triggered_tier=1,
            det_overall=det_overall,
            llm_overall=llm_overall,
            composite=composite,
            reason="Tier 1: 문법 오류 – 실행 불가 코드 즉시 차단",
        )

    if det_security < TIER1_SEC_MIN:
        return GateDecision(
            sample_id=sample_id,
            outcome=GateOutcome.BLOCKED,
            triggered_tier=1,
            det_overall=det_overall,
            llm_overall=llm_overall,
            composite=composite,
            reason=(
                f"Tier 1: 결정론적 보안 점수 {det_security} < {TIER1_SEC_MIN}"
                " – 심각한 보안 취약점"
            ),
        )

    # ── Tier 2: Soft Gate (LLM 보조) ──────────────────────────────────────
    if llm_overall < TIER2_LLM_MIN:
        return GateDecision(
            sample_id=sample_id,
            outcome=GateOutcome.REVIEW_REQUIRED,
            triggered_tier=2,
            det_overall=det_overall,
            llm_overall=llm_overall,
            composite=composite,
            reason=(
                f"Tier 2: LLM Judge 점수 {llm_overall} < {TIER2_LLM_MIN}"
                " – 사람 리뷰 필요 (LLM 단독 pass/fail 아님)"
            ),
        )

    # ── Tier 3: Composite Score ────────────────────────────────────────────
    if composite >= TIER3_PASS_THRESHOLD:
        return GateDecision(
            sample_id=sample_id,
            outcome=GateOutcome.PASS,
            triggered_tier=3,
            det_overall=det_overall,
            llm_overall=llm_overall,
            composite=composite,
            reason=f"Tier 3: 합성 점수 {composite} >= {TIER3_PASS_THRESHOLD} – PASS",
        )
    elif composite >= TIER3_COND_THRESHOLD:
        return GateDecision(
            sample_id=sample_id,
            outcome=GateOutcome.CONDITIONAL_PASS,
            triggered_tier=3,
            det_overall=det_overall,
            llm_overall=llm_overall,
            composite=composite,
            reason=(
                f"Tier 3: 합성 점수 {composite} in [{TIER3_COND_THRESHOLD}, {TIER3_PASS_THRESHOLD})"
                " – 조건부 통과, 사람 리뷰 권장"
            ),
        )
    else:
        return GateDecision(
            sample_id=sample_id,
            outcome=GateOutcome.FAIL,
            triggered_tier=3,
            det_overall=det_overall,
            llm_overall=llm_overall,
            composite=composite,
            reason=f"Tier 3: 합성 점수 {composite} < {TIER3_COND_THRESHOLD} – FAIL",
        )


def evaluate_all_gates(
    sample_ids:   list[int],
    syntax_oks:   list[bool],
    det_secs:     list[float],
    det_overalls: list[float],
    llm_overalls: list[float],
) -> list[GateDecision]:
    return [
        evaluate_gate(sid, syn, sec, det, llm)
        for sid, syn, sec, det, llm
        in zip(sample_ids, syntax_oks, det_secs, det_overalls, llm_overalls)
    ]


# ─────────────────────────────────────────────────────────────────────────────
# 편향 완화(Mitigation) 전략
# ─────────────────────────────────────────────────────────────────────────────

BIAS_REPORT = {
    # ── 편향 #1 (주): Security Blind Spot Bias ──────────────────────────────
    "primary_bias": "Security Blind Spot Bias – LLM 이 보안 취약점 심각도를 과소평가",
    "primary_evidence": (
        "Sample 3 (SQL 인젝션):      인간 2.0 → LLM 5.5  (오차 +3.5)\n"
        "Sample 8 (하드코딩 자격증명): 인간 2.0 → LLM 6.0  (오차 +4.0)\n"
        "OWASP 상위 취약점에 대해 LLM 은 일관되게 3-4점 과대평가."
    ),
    # ── 편향 #2 (부): Length Bias ──────────────────────────────────────────
    "secondary_bias": "Length Bias – 장황한 코드에 가독성 점수를 더 높게 부여하는 경향",
    "secondary_evidence": (
        "Sample 5 (42줄, 과도 주석): 인간 6.0 → LLM 8.0  (오차 +2.0)\n"
        "Sample 6 (3줄, 간결):       인간 8.0 → LLM 7.8  (오차 -0.2)\n"
        "줄 수 vs LLM-Human 오차 Pearson r=+0.19 (p=0.61, n=10)\n"
        "소표본(n=10)에서 통계적 유의성은 낮으나 방향성은 일관됨."
    ),
    "mitigations": [
        {
            "strategy": "Tier 1 Hard Gate – 결정론적 선행 필터 (Security Blind Spot 대응)",
            "description": (
                "보안 점수 < 5.0 이면 LLM 점수와 무관하게 즉시 BLOCKED. "
                "LLM 이 SQL 인젝션을 5.5/10 으로 과소평가해도 Tier 1 에서 차단됨. "
                "결정론적 패턴 탐지가 보안 사각지대를 보완."
            ),
        },
        {
            "strategy": "프롬프트 명시적 편향 억제 (Length Bias 대응)",
            "description": (
                "시스템 프롬프트에 '코드 길이 자체는 점수에 영향을 주지 않도록'을 "
                "명시적으로 지시. llm_judge.py _SYSTEM_PROMPT 참조. "
                "평가 전 코드 정규화(주석 제거) 후 입력하는 방법도 유효."
            ),
        },
        {
            "strategy": "복합 가중치 조정 (두 편향 모두 희석)",
            "description": (
                "결정론적 평가 가중치 60%, LLM 가중치 40% 로 제한하여 "
                "LLM 편향이 최종 결정에 미치는 영향을 구조적으로 축소."
            ),
        },
        {
            "strategy": "다수 LLM 앙상블 + 중앙값 취합 (Security Blind Spot 대응)",
            "description": (
                "동일 코드를 복수 모델(GPT-4o, Claude, Gemini)로 평가한 뒤 "
                "중앙값을 사용하면 단일 모델의 보안 사각지대 영향을 줄일 수 있음."
            ),
        },
    ],
}
