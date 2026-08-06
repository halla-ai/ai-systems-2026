"""
span_evidence.py — otel_spans_*.json 을 읽어
7개 필수 span attribute 존재 여부를 검증·리포트
"""

import json
import glob
import sys

REQUIRED_ATTRS = [
    "run.id",
    "task.id",
    "agent.role",
    "model.name",
    "tool.name",
    "gate.result",
    "artifact.path",
]

PASS = "✓ PASS"
FAIL = "✗ FAIL"
SEP  = "─" * 62


def check_spans(spans_file: str) -> bool:
    with open(spans_file, "r", encoding="utf-8") as f:
        spans = json.load(f)

    total      = len(spans)
    all_pass   = True
    pass_count = 0

    print(f"\n{'='*62}")
    print(f"  OTel Span Attribute Evidence Report")
    print(f"  Source : {spans_file}")
    print(f"  Spans  : {total}")
    print(f"{'='*62}\n")
    print(f"  {'Span Name':<22}  {'Status':<8}  Missing / Attributes")
    print(f"  {SEP}")

    for sp in spans:
        attrs   = sp.get("attributes", {})
        missing = [a for a in REQUIRED_ATTRS if a not in attrs]
        ok      = len(missing) == 0
        status  = PASS if ok else FAIL
        if ok:
            pass_count += 1
        else:
            all_pass = False

        print(f"  {sp['span_name']:<22}  {status}")
        for attr in REQUIRED_ATTRS:
            val = attrs.get(attr, "<MISSING>")
            flag = "  " if attr not in missing else "⚠ "
            print(f"      {flag}{attr:<20} = {str(val)!r}")
        print()

    print(f"  {SEP}")
    print(f"  Spans with ALL 7 attrs : {pass_count} / {total}")
    print(f"  Required attributes    : {len(REQUIRED_ATTRS)}")
    for a in REQUIRED_ATTRS:
        print(f"      • {a}")
    print(f"\n  Overall result : {'ALL PASS ✓' if all_pass else 'SOME FAILED ✗'}")
    print(f"{'='*62}\n")
    return all_pass


if __name__ == "__main__":
    files = sorted(glob.glob("otel_spans_*.json"))
    if not files:
        print("No otel_spans_*.json found. Run agent_harness.py first.")
        sys.exit(1)
    ok = check_spans(files[-1])
    sys.exit(0 if ok else 1)
