"""
statistical_analysis.py
-----------------------
세 평가 방법 간 상관관계 분석.

  - Pearson r  : 선형 상관 (정규분포 가정)
  - Spearman ρ : 순위 기반 상관 (분포 무관, 소표본에 적합)
  - n = 10, 양방향 p-value 보고

분석 쌍
  A) 결정론적 vs 인간
  B) LLM Judge vs 인간
  C) 결정론적 vs LLM Judge
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy import stats


# ─────────────────────────────────────────────────────────────────────────────
# 출력 자료구조
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class CorrelationResult:
    pair: str           # 예: "LLM vs Human"
    n: int
    pearson_r: float
    pearson_p: float
    spearman_r: float
    spearman_p: float

    # 해석 레이블
    @staticmethod
    def _strength(r: float) -> str:
        a = abs(r)
        if a >= 0.90: return "매우 강함"
        if a >= 0.70: return "강함"
        if a >= 0.50: return "중간"
        if a >= 0.30: return "약함"
        return "매우 약함"

    @staticmethod
    def _sig(p: float) -> str:
        if p < 0.001: return "***"
        if p < 0.01:  return "**"
        if p < 0.05:  return "*"
        return "n.s."

    def summary(self) -> str:
        pr = f"r={self.pearson_r:+.3f}  p={self.pearson_p:.4f}{self._sig(self.pearson_p)}"
        sr = f"ρ={self.spearman_r:+.3f}  p={self.spearman_p:.4f}{self._sig(self.spearman_p)}"
        return (
            f"[{self.pair}]  n={self.n}\n"
            f"  Pearson  : {pr}  ({self._strength(self.pearson_r)})\n"
            f"  Spearman : {sr}  ({self._strength(self.spearman_r)})"
        )


# ─────────────────────────────────────────────────────────────────────────────
# 핵심 계산 함수
# ─────────────────────────────────────────────────────────────────────────────

def _correlate(pair: str, x: list[float], y: list[float]) -> CorrelationResult:
    xa = np.array(x, dtype=float)
    ya = np.array(y, dtype=float)
    n = len(xa)

    pr, pp = stats.pearsonr(xa, ya)
    sr, sp = stats.spearmanr(xa, ya)

    return CorrelationResult(
        pair=pair,
        n=n,
        pearson_r=round(float(pr), 4),
        pearson_p=round(float(pp), 4),
        spearman_r=round(float(sr), 4),
        spearman_p=round(float(sp), 4),
    )


def run_analysis(
    human_scores:  list[float],
    llm_scores:    list[float],
    det_scores:    list[float],
) -> list[CorrelationResult]:
    """
    세 평가 방법 간 2×3 쌍 상관계수를 계산해 반환.

    Parameters
    ----------
    human_scores  : 인간 평가 overall (n=10)
    llm_scores    : LLM Judge overall (n=10)
    det_scores    : 결정론적 평가 overall (n=10)
    """
    return [
        _correlate("Deterministic vs Human", det_scores,  human_scores),
        _correlate("LLM Judge vs Human",     llm_scores,  human_scores),
        _correlate("Deterministic vs LLM",   det_scores,  llm_scores),
    ]


# ─────────────────────────────────────────────────────────────────────────────
# 편향 분석 보조 함수
# ─────────────────────────────────────────────────────────────────────────────

def detect_length_bias(
    sample_ids:   list[int],
    codes:        list[str],
    llm_scores:   list[float],
    human_scores: list[float],
) -> dict:
    """
    LLM 길이 편향(length bias) 정량 분석.

    각 샘플에 대해 (코드 라인 수) 와 (LLM - Human 점수 오차) 간
    Pearson/Spearman 상관을 계산.
    양의 상관 → 긴 코드일수록 LLM 이 과대평가.
    """
    line_counts = [len(c.strip().splitlines()) for c in codes]
    errors      = [llm - hum for llm, hum in zip(llm_scores, human_scores)]

    pr, pp = stats.pearsonr(line_counts, errors)
    sr, sp = stats.spearmanr(line_counts, errors)

    # 가장 과대평가된 샘플
    max_err_idx = int(np.argmax(errors))
    min_err_idx = int(np.argmin(errors))

    return {
        "bias_name": "Length Bias (줄 수 ↑ → LLM 점수 과대평가)",
        "pearson_r": round(float(pr), 4),
        "pearson_p": round(float(pp), 4),
        "spearman_r": round(float(sr), 4),
        "spearman_p": round(float(sp), 4),
        "most_overrated_sample_id":  sample_ids[max_err_idx],
        "most_underrated_sample_id": sample_ids[min_err_idx],
        "line_counts": dict(zip(sample_ids, line_counts)),
        "llm_minus_human_errors": dict(zip(sample_ids, [round(e, 2) for e in errors])),
    }
