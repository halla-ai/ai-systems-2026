"""
human_scores.py
---------------
Lab 12 인간 평가 데이터.

시나리오: 3인의 숙련 개발자가 각 샘플을 0-10 으로 독립 평가.
최종 human_score 는 세 평가자의 평균(소수점 1자리).

평가 기준 안내서 (평가자에게 배포):
  10 : 프로덕션 즉시 투입 가능한 이상적 코드
   8 : 사소한 스타일 이슈만 있음
   6 : 동작하나 개선 여지가 많음
   4 : 중요한 버그 또는 보안 이슈 1개
   2 : 심각한 결함 복수 (보안 취약점·다수 버그 등)
   0 : 실행 불가 / 완전히 잘못된 코드
"""

from __future__ import annotations
from dataclasses import dataclass


@dataclass
class HumanEval:
    sample_id: int
    reviewer_a: float
    reviewer_b: float
    reviewer_c: float
    mean: float          # (a+b+c) / 3
    rationale: str


_RAW: list[dict] = [
    {
        "sample_id": 1,
        "reviewer_a": 9.0, "reviewer_b": 9.0, "reviewer_c": 9.0,
        "rationale": "모든 평가자가 만점에 가깝게 평가. "
                     "정확·효율·가독성 모두 우수한 교과서적 이진 탐색.",
    },
    {
        "sample_id": 2,
        "reviewer_a": 5.0, "reviewer_b": 5.0, "reviewer_c": 5.0,
        "rationale": "동작은 하나 조기 종료 없는 O(n²) 구현. "
                     "성능 개선 여지가 명확하므로 중간 점수.",
    },
    {
        "sample_id": 3,
        "reviewer_a": 2.0, "reviewer_b": 2.0, "reviewer_c": 2.0,
        "rationale": "SQL 인젝션 취약점(OWASP A03). "
                     "보안 전문가 모두 즉각 거부. 기능 자체는 동작하므로 0점은 아님.",
    },
    {
        "sample_id": 4,
        "reviewer_a": 3.0, "reviewer_b": 3.0, "reviewer_c": 3.0,
        "rationale": "off-by-one 버그로 항상 잘못된 결과 반환. "
                     "낮은 점수지만 구조 자체는 단순·명확.",
    },
    {
        "sample_id": 5,
        "reviewer_a": 6.0, "reviewer_b": 6.0, "reviewer_c": 6.0,
        "rationale": "정확하지만 과도한 주석이 오히려 가독성을 저해. "
                     "내장 sum() 미사용, 장황한 docstring. 보통 점수.",
    },
    {
        "sample_id": 6,
        "reviewer_a": 8.0, "reviewer_b": 8.0, "reviewer_c": 8.0,
        "rationale": "Pythonic 원라이너, 타입 힌트 포함, 엣지케이스 처리. "
                     "간결함 자체가 장점. 일부 주석 보완이면 만점.",
    },
    {
        "sample_id": 7,
        "reviewer_a": 5.0, "reviewer_b": 5.0, "reviewer_c": 5.0,
        "rationale": "동작하나 미사용 변수·사문 코드·의미없는 else-pass 로 "
                     "유지보수성 저하. 중간 점수.",
    },
    {
        "sample_id": 8,
        "reviewer_a": 2.0, "reviewer_b": 2.0, "reviewer_c": 2.0,
        "rationale": "하드코딩 자격증명(OWASP A02). "
                     "소스코드에 시크릿 포함 – 즉시 거부 수준.",
    },
    {
        "sample_id": 9,
        "reviewer_a": 1.0, "reviewer_b": 1.0, "reviewer_c": 1.0,
        "rationale": "문법 오류 다수로 실행 불가. NameError 까지 존재. "
                     "최하점 부근.",
    },
    {
        "sample_id": 10,
        "reviewer_a": 5.0, "reviewer_b": 5.0, "reviewer_c": 5.0,
        "rationale": "동작하나 단순 덧셈에 Factory+Strategy 패턴은 "
                     "명백한 과설계. 유지보수 부담만 늘어남.",
    },
]


def load_human_scores() -> list[HumanEval]:
    results: list[HumanEval] = []
    for r in _RAW:
        a, b, c = r["reviewer_a"], r["reviewer_b"], r["reviewer_c"]
        results.append(
            HumanEval(
                sample_id=r["sample_id"],
                reviewer_a=a,
                reviewer_b=b,
                reviewer_c=c,
                mean=round((a + b + c) / 3, 1),
                rationale=r["rationale"],
            )
        )
    return results
