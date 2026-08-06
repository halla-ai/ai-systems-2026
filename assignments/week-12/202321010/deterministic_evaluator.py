"""
deterministic_evaluator.py
--------------------------
순수 규칙 기반(결정론적) 코드 품질 평가기.

Python 표준 라이브러리(ast, re)만 사용.

채점 항목
  syntax_ok      : AST 파싱 성공 여부 (bool)
  security_score : 보안 패턴 탐지 기반 (0-10)
  bug_score      : 알려진 버그 패턴 탐지 (0-10)
  style_score    : 사문 코드·미사용 변수 탐지 (0-10)
  complexity     : 분기/루프 수 (raw int)
  overall        : 가중 합산 (0-10)
"""

from __future__ import annotations

import ast
import re
from dataclasses import asdict, dataclass
from typing import Optional


# ─────────────────────────────────────────────────────────────────────────────
# 출력 스키마
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class DetResult:
    sample_id: int
    syntax_ok: bool
    security_score: float   # 0-10 (높을수록 안전)
    bug_score: float        # 0-10 (높을수록 버그 없음)
    style_score: float      # 0-10 (높을수록 깔끔)
    complexity: int         # 분기+루프 수 (낮을수록 단순)
    overall: float          # 가중 평균 0-10
    flags: list[str]        # 탐지된 문제 목록

    def to_dict(self) -> dict:
        return asdict(self)


# ─────────────────────────────────────────────────────────────────────────────
# 보안 패턴 (regex 기반)
# ─────────────────────────────────────────────────────────────────────────────

_SECURITY_PATTERNS: list[tuple[str, str, float]] = [
    # (pattern, description, penalty_per_occurrence)
    # ── SQL 인젝션 탐지 ──────────────────────────────────────────────────
    (r"execute\s*\(\s*['\"].*\+",
        "SQL 인라인 문자열 연결(인젝션 위험)", 6.0),
    (r'execute\s*\(\s*f["\']',
        "f-string SQL 쿼리(인젝션 위험)", 6.0),
    # 변수로 빌드된 SQL: SELECT/INSERT/... 키워드 포함 문자열 + 파이썬 '+' 연결
    (r'(?i)(SELECT|INSERT|UPDATE|DELETE|DROP)\b.+["\'].*\+',
        "SQL 쿼리 변수 문자열 연결(인젝션 위험)", 6.0),
    # ── 자격증명 하드코딩 탐지 (각 항목별 카운트) ───────────────────────
    (r'(?i)(password|passwd|pwd)\s*=\s*["\'][^"\']{4,}["\']',
        "패스워드 하드코딩", 5.0),
    (r'(?i)(secret|api_?key|token|access_?key)\s*=\s*["\'][^"\']{4,}["\']',
        "시크릿/API Key 하드코딩", 5.0),
    # ── 기타 위험 패턴 ───────────────────────────────────────────────────
    (r'eval\s*\(',                 "eval() 사용(코드 인젝션 위험)", 4.0),
    (r'exec\s*\(',                 "exec() 사용(코드 인젝션 위험)", 4.0),
    (r'pickle\.loads?\s*\(',       "pickle 역직렬화(임의코드 실행)", 3.0),
    (r'subprocess.*shell\s*=\s*True', "shell=True subprocess(명령어 인젝션)", 4.0),
]


def _security_score(code: str) -> tuple[float, list[str]]:
    """각 패턴의 모든 발생 횟수를 카운트하여 패널티를 누적."""
    flags: list[str] = []
    penalty = 0.0
    for pattern, desc, pen in _SECURITY_PATTERNS:
        matches = re.findall(pattern, code)
        count = len(matches)
        if count > 0:
            label = f"[SECURITY] {desc}" + (f" (×{count}건)" if count > 1 else "")
            flags.append(label)
            penalty += pen * count
    score = max(0.0, 10.0 - penalty)
    return round(score, 1), flags


# ─────────────────────────────────────────────────────────────────────────────
# 버그 패턴 (AST + regex 기반)
# ─────────────────────────────────────────────────────────────────────────────

def _bug_score(code: str, tree: Optional[ast.AST]) -> tuple[float, list[str]]:
    flags: list[str] = []
    penalty = 0.0

    # off-by-one: range(len(x) - 1) 패턴
    if re.search(r'range\s*\(\s*len\s*\(.+\)\s*-\s*1\s*\)', code):
        flags.append("[BUG] off-by-one 의심: range(len(x)-1)")
        penalty += 5.0

    # 변수명 오타 탐지 (정의되지 않은 이름 사용): AST 기반
    if tree is not None:
        defined: set[str] = set()
        used:    set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for arg in node.args.args:
                    defined.add(arg.arg)
            if isinstance(node, (ast.Assign, ast.AnnAssign)):
                if isinstance(node, ast.Assign):
                    for t in node.targets:
                        if isinstance(t, ast.Name):
                            defined.add(t.id)
                else:
                    if isinstance(node.target, ast.Name):
                        defined.add(node.target.id)
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
                used.add(node.id)

        # 내장 함수·키워드 제외
        builtins = {
            "None", "True", "False", "print", "len", "range", "sum",
            "min", "max", "int", "float", "str", "list", "dict", "set",
            "tuple", "type", "isinstance", "hasattr", "getattr", "setattr",
            "enumerate", "zip", "map", "filter", "sorted", "reversed",
            "abs", "round", "open", "Exception", "ValueError", "KeyError",
            "TypeError", "IndexError", "RuntimeError", "NotImplementedError",
        }
        undefined = used - defined - builtins
        # 짧은 이름(한 글자) 및 일반적인 패턴 제외
        undefined = {n for n in undefined if len(n) > 2}
        if undefined:
            flags.append(f"[BUG] 정의되지 않은 이름 사용 의심: {', '.join(sorted(undefined))}")
            penalty += min(len(undefined) * 2.0, 6.0)

    score = max(0.0, 10.0 - penalty)
    return round(score, 1), flags


# ─────────────────────────────────────────────────────────────────────────────
# 코드 스타일 (사문 코드, 미사용 변수 등)
# ─────────────────────────────────────────────────────────────────────────────

def _style_score(code: str, tree: Optional[ast.AST]) -> tuple[float, list[str]]:
    flags: list[str] = []
    penalty = 0.0

    # else: pass 패턴
    if re.search(r'else\s*:\s*\n\s*pass', code):
        flags.append("[STYLE] 의미 없는 else: pass 구문")
        penalty += 1.5

    # if False: 도달 불가 코드
    if re.search(r'if\s+False\s*:', code):
        flags.append("[STYLE] 도달 불가 코드: if False:")
        penalty += 2.0

    # AST 기반 미사용 변수 탐지
    if tree is not None:
        assigned: dict[str, int] = {}
        used_names: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for t in node.targets:
                    if isinstance(t, ast.Name):
                        assigned[t.id] = assigned.get(t.id, 0) + 1
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
                used_names.add(node.id)

        unused = {
            name for name in assigned
            if name not in used_names and not name.startswith("_")
        }
        if unused:
            flags.append(f"[STYLE] 미사용 변수: {', '.join(sorted(unused))}")
            penalty += min(len(unused) * 1.0, 3.0)

    score = max(0.0, 10.0 - penalty)
    return round(score, 1), flags


# ─────────────────────────────────────────────────────────────────────────────
# 사이클로매틱 복잡도 (근사치)
# ─────────────────────────────────────────────────────────────────────────────

def _cyclomatic(tree: Optional[ast.AST]) -> int:
    if tree is None:
        return 0
    count = 1
    for node in ast.walk(tree):
        if isinstance(node, (ast.If, ast.For, ast.While, ast.ExceptHandler,
                              ast.With, ast.Assert, ast.comprehension)):
            count += 1
        elif isinstance(node, ast.BoolOp):
            count += len(node.values) - 1
    return count


# ─────────────────────────────────────────────────────────────────────────────
# 공개 평가 함수
# ─────────────────────────────────────────────────────────────────────────────

def evaluate(sample_id: int, code: str) -> DetResult:
    """코드를 결정론적으로 평가하고 DetResult 반환."""
    flags: list[str] = []

    # 1) 문법 검사
    tree: Optional[ast.AST] = None
    try:
        tree = ast.parse(code)
        syntax_ok = True
    except SyntaxError as e:
        syntax_ok = False
        flags.append(f"[SYNTAX] SyntaxError: {e}")

    # 2) 보안 점수
    sec_score, sec_flags = _security_score(code)
    flags.extend(sec_flags)

    # 3) 버그 점수
    bug_sc, bug_flags = _bug_score(code, tree)
    flags.extend(bug_flags)

    # 4) 스타일 점수
    sty_sc, sty_flags = _style_score(code, tree)
    flags.extend(sty_flags)

    # 5) 복잡도
    complexity = _cyclomatic(tree)

    # 6) syntax 실패 시 점수 보정
    if not syntax_ok:
        sec_score = 0.0
        bug_sc    = 0.0
        sty_sc    = 0.0

    # 7) overall (가중 평균)
    #    syntax 가중 = 0.25, security = 0.30, bug = 0.30, style = 0.15
    syntax_val = 10.0 if syntax_ok else 0.0
    overall = round(
        0.25 * syntax_val
        + 0.30 * sec_score
        + 0.30 * bug_sc
        + 0.15 * sty_sc,
        1,
    )

    return DetResult(
        sample_id=sample_id,
        syntax_ok=syntax_ok,
        security_score=sec_score,
        bug_score=bug_sc,
        style_score=sty_sc,
        complexity=complexity,
        overall=overall,
        flags=flags,
    )


def evaluate_all(samples: list[dict]) -> list[DetResult]:
    return [evaluate(s["id"], s["code"]) for s in samples]
