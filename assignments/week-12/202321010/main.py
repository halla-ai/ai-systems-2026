"""
main.py
-------
Lab 12 전체 파이프라인 실행기.

출력:
  1) LLM Judge strict JSON 샘플 (첫 번째 샘플)
  2) 10개 샘플 자동 평가 비교표 (결정론적 / LLM / 인간)
  3) Spearman / Pearson 상관계수 (n, p-value 포함)
  4) 게이트 정책 결과
  5) 관찰된 편향 보고 및 완화 전략
"""

from __future__ import annotations

import json
import textwrap

import numpy as np

# ── 로컬 모듈 ──────────────────────────────────────────────────────────────
from code_samples         import SAMPLES
from llm_judge            import LLMJudge
from deterministic_evaluator import evaluate_all as det_evaluate_all
from human_scores         import load_human_scores
from statistical_analysis import run_analysis, detect_length_bias
from gate_policy          import (
    evaluate_all_gates,
    BIAS_REPORT,
)

try:
    from tabulate import tabulate
    _HAS_TABULATE = True
except ImportError:
    _HAS_TABULATE = False


# ─────────────────────────────────────────────────────────────────────────────
# 유틸리티
# ─────────────────────────────────────────────────────────────────────────────

def _sep(title: str = "", width: int = 72) -> None:
    if title:
        pad = (width - len(title) - 2) // 2
        print("─" * pad + f" {title} " + "─" * (width - pad - len(title) - 2))
    else:
        print("─" * width)


def _table(headers: list[str], rows: list[list], **kwargs) -> str:
    if _HAS_TABULATE:
        return tabulate(rows, headers=headers, tablefmt="simple", **kwargs)
    # 간이 테이블 출력
    col_w = [max(len(str(h)), max((len(str(r[i])) for r in rows), default=0))
             for i, h in enumerate(headers)]
    fmt = "  ".join(f"{{:<{w}}}" for w in col_w)
    lines = [fmt.format(*headers)]
    lines.append("  ".join("-" * w for w in col_w))
    for row in rows:
        lines.append(fmt.format(*[str(x) for x in row]))
    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# Step 1: 평가 실행
# ─────────────────────────────────────────────────────────────────────────────

def run_evaluation():
    judge   = LLMJudge(mode="auto")   # API 키 없으면 자동으로 mock
    llm_results = judge.evaluate_all(SAMPLES)
    det_results = det_evaluate_all(SAMPLES)
    human_evals = load_human_scores()
    return llm_results, det_results, human_evals


# ─────────────────────────────────────────────────────────────────────────────
# Step 2: Strict JSON 샘플 출력
# ─────────────────────────────────────────────────────────────────────────────

def print_json_sample(llm_results):
    _sep("Section 1: LLM Judge Strict JSON 출력 (Sample 1)")
    print(llm_results[0].to_strict_json())
    print()


# ─────────────────────────────────────────────────────────────────────────────
# Step 3: 3-방법 비교표
# ─────────────────────────────────────────────────────────────────────────────

def print_comparison_table(llm_results, det_results, human_evals):
    _sep("Section 2: 10개 샘플 평가 비교표")

    # 인덱스 맵
    llm_map  = {r.sample_id: r for r in llm_results}
    det_map  = {r.sample_id: r for r in det_results}
    hum_map  = {e.sample_id: e for e in human_evals}

    headers = [
        "ID", "샘플명",
        "Det.\nOverall", "LLM\nOverall", "Human\nMean",
        "Det-Hum\nΔ", "LLM-Hum\nΔ",
    ]
    rows = []
    for s in SAMPLES:
        sid   = s["id"]
        name  = s["name"][:28]
        det   = det_map[sid].overall
        llm   = llm_map[sid].overall
        hum   = hum_map[sid].mean
        d_h   = round(det - hum, 1)
        l_h   = round(llm - hum, 1)
        rows.append([
            sid, name,
            f"{det:.1f}", f"{llm:.1f}", f"{hum:.1f}",
            f"{d_h:+.1f}", f"{l_h:+.1f}",
        ])

    print(_table(headers, rows, floatfmt=".1f"))
    print()

    # 요약 통계
    det_arr  = np.array([det_map[s["id"]].overall  for s in SAMPLES])
    llm_arr  = np.array([llm_map[s["id"]].overall  for s in SAMPLES])
    hum_arr  = np.array([hum_map[s["id"]].mean     for s in SAMPLES])
    print(f"  평균  – Det: {det_arr.mean():.2f}  LLM: {llm_arr.mean():.2f}  Human: {hum_arr.mean():.2f}")
    print(f"  표준편차 – Det: {det_arr.std():.2f}  LLM: {llm_arr.std():.2f}  Human: {hum_arr.std():.2f}")
    print()


# ─────────────────────────────────────────────────────────────────────────────
# Step 4: 상관계수
# ─────────────────────────────────────────────────────────────────────────────

def print_correlation(llm_results, det_results, human_evals):
    _sep("Section 3: Pearson / Spearman 상관계수 (n=10)")

    llm_map  = {r.sample_id: r for r in llm_results}
    det_map  = {r.sample_id: r for r in det_results}
    hum_map  = {e.sample_id: e for e in human_evals}

    sample_ids   = [s["id"] for s in SAMPLES]
    human_scores = [hum_map[sid].mean        for sid in sample_ids]
    llm_scores   = [llm_map[sid].overall     for sid in sample_ids]
    det_scores   = [det_map[sid].overall     for sid in sample_ids]

    results = run_analysis(human_scores, llm_scores, det_scores)
    for cr in results:
        print(cr.summary())
        print()

    # Significance 설명
    print("  * p<0.05  ** p<0.01  *** p<0.001  n.s.: not significant")
    print("  주의: n=10 소표본에서 p-value 는 크게 나타날 수 있음.")
    print()

    return sample_ids, human_scores, llm_scores, det_scores


# ─────────────────────────────────────────────────────────────────────────────
# Step 5: 게이트 정책
# ─────────────────────────────────────────────────────────────────────────────

def print_gate_policy(llm_results, det_results):
    _sep("Section 4: Gate Policy 적용 결과")

    llm_map = {r.sample_id: r for r in llm_results}
    det_map = {r.sample_id: r for r in det_results}

    sample_ids   = [s["id"]                      for s in SAMPLES]
    syntax_oks   = [det_map[sid].syntax_ok        for sid in sample_ids]
    det_secs     = [det_map[sid].security_score   for sid in sample_ids]
    det_overalls = [det_map[sid].overall          for sid in sample_ids]
    llm_overalls = [llm_map[sid].overall          for sid in sample_ids]

    decisions = evaluate_all_gates(
        sample_ids, syntax_oks, det_secs, det_overalls, llm_overalls
    )

    headers = ["ID", "샘플명", "Det", "LLM", "Comp.", "Tier", "결과", "근거(요약)"]
    rows = []
    for d, s in zip(decisions, SAMPLES):
        rows.append([
            d.sample_id,
            s["name"][:24],
            f"{d.det_overall:.1f}",
            f"{d.llm_overall:.1f}",
            f"{d.composite:.2f}",
            d.triggered_tier,
            d.outcome.emoji(),
            d.reason[:52] + "…" if len(d.reason) > 52 else d.reason,
        ])

    print(_table(headers, rows))
    print()

    outcomes = [d.outcome.value for d in decisions]
    from collections import Counter
    cnt = Counter(outcomes)
    print("  결과 분포:", dict(cnt))
    print()

    # 정책 근거 설명
    _sep("Gate Policy 설계 근거")
    rationale = textwrap.dedent("""\
    LLM Judge 를 직접 pass/fail 게이트로 사용하지 않는 이유:

    1. 비결정론성  : 동일 코드에 대해 실행마다 점수가 달라질 수 있어
                     CI/CD 파이프라인에서 재현성 보장 불가.

    2. 편향 존재   : Length Bias 등으로 짧고 우아한 코드가
                     거부(Sample 6: Human 8.0 → LLM 6.4)될 수 있음.

    3. 보안 사각   : SQL 인젝션·하드코딩 자격증명을 탐지하더라도
                     결정론적 패턴 매칭보다 신뢰성이 낮음.

    4. 조작 가능성 : 장황한 주석·긴 변수명으로 점수를 높일 수 있음.

    따라서 LLM Judge 는 결정론적 검사의 '보완 신호'로만 사용하며,
    가중치(40%)를 제한하고 Tier 1 하드 게이트 이후에만 참조함.
    """)
    print(rationale)


# ─────────────────────────────────────────────────────────────────────────────
# Step 6: 편향 보고
# ─────────────────────────────────────────────────────────────────────────────

def print_bias_report(sample_ids, llm_scores, human_scores):
    _sep("Section 5: 관찰된 Judge Bias 및 Mitigation")

    codes = [s["code"] for s in SAMPLES]
    bias  = detect_length_bias(sample_ids, codes, llm_scores, human_scores)

    # ── 편향 #1 (주): Security Blind Spot ────────────────────────────────
    print("  ■ 편향 #1 (주요): Security Blind Spot Bias")
    print(f"    {BIAS_REPORT['primary_bias']}")
    print()
    for line in BIAS_REPORT["primary_evidence"].splitlines():
        print(f"    {line}")
    print()

    # ── 편향 #2 (부): Length Bias ─────────────────────────────────────────
    print("  ■ 편향 #2 (부): Length Bias")
    print(f"    {BIAS_REPORT['secondary_bias']}")
    print()
    print(f"    Pearson r  = {bias['pearson_r']:+.4f},  p = {bias['pearson_p']:.4f}")
    print(f"    Spearman ρ = {bias['spearman_r']:+.4f},  p = {bias['spearman_p']:.4f}")
    print()
    print("    줄 수 vs LLM-Human 오차 (샘플별):")
    headers2 = ["Sample ID", "줄 수", "LLM-Human 오차"]
    rows2    = [
        [sid,
         bias["line_counts"][sid],
         f"{bias['llm_minus_human_errors'][sid]:+.2f}"]
        for sid in sample_ids
    ]
    print(textwrap.indent(_table(headers2, rows2), "    "))
    print()

    # ── Mitigation 전략 ────────────────────────────────────────────────────
    _sep("Mitigation 전략 (4가지)")
    for i, m in enumerate(BIAS_REPORT["mitigations"], 1):
        print(f"  {i}. [{m['strategy']}]")
        for line in textwrap.wrap(m["description"], width=66):
            print(f"     {line}")
        print()


# ─────────────────────────────────────────────────────────────────────────────
# 메인
# ─────────────────────────────────────────────────────────────────────────────

def main():
    _sep("Lab 12: LLM Judge 평가 시스템", width=72)
    print()

    print("평가 실행 중 ...\n")
    llm_results, det_results, human_evals = run_evaluation()

    print_json_sample(llm_results)
    print_comparison_table(llm_results, det_results, human_evals)
    sample_ids, human_scores, llm_scores, det_scores = print_correlation(
        llm_results, det_results, human_evals
    )
    print_gate_policy(llm_results, det_results)
    print_bias_report(sample_ids, llm_scores, human_scores)

    _sep("완료", width=72)


if __name__ == "__main__":
    main()
