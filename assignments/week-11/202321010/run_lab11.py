"""
run_lab11.py — Lab 11 메인 실행 스크립트
  Step 1. RALPH Agent Harness (OTel 트레이싱)  → *.events.jsonl, otel_spans_*.json
  Step 2. Replay Engine                         → replay_snapshot.json
  Step 3. Dashboard                             → dashboard.png, dashboard_data.csv
  Step 4. Span Attribute Evidence               → 콘솔 출력
"""

import glob
import sys


def main():
    print("=" * 62)
    print("  Lab 11 - OpenTelemetry RALPH Agent Harness")
    print("  2026-05-25  •  202321010")
    print("=" * 62)

    # ── Step 1: 에이전트 하네스 실행 ───────────────────────────────────────────
    print("\n[1/4] Running RALPH agent harness with OpenTelemetry tracing...")
    from agent_harness import run_harness
    run_id, total_cost, events_file, spans_file = run_harness()

    # ── Step 2: 이벤트 재계산 ──────────────────────────────────────────────────
    print("\n[2/4] Replaying events → replay_snapshot.json ...")
    from replay import replay
    replay(events_file)

    # ── Step 3: 대시보드 ────────────────────────────────────────────────────────
    print("\n[3/4] Generating 4-panel dashboard → dashboard.png ...")
    from dashboard import build_dashboard
    build_dashboard(events_file)

    # ── Step 4: 스팬 속성 검증 ─────────────────────────────────────────────────
    print("\n[4/4] Verifying 7 required span attributes ...")
    from span_evidence import check_spans
    all_ok = check_spans(spans_file)

    # ── 최종 요약 ──────────────────────────────────────────────────────────────
    print("=" * 62)
    print("  Lab 11 Complete - Generated Files")
    print("=" * 62)
    print(f"  {events_file:<40} (Agent OS Runtime .events.jsonl)")
    print(f"  replay_snapshot.json                     (Replay recalculated output)")
    print(f"  dashboard.png                            (4-panel dashboard screenshot)")
    print(f"  dashboard_data.csv                       (Raw CSV data)")
    print(f"  {spans_file:<40} (OTel span attribute evidence)")
    print("=" * 62)
    print(f"  run_id      : {run_id}")
    print(f"  total_cost  : ${total_cost:.8f}")
    print(f"  span attrs  : {'ALL 7 PASS ✓' if all_ok else 'CHECK FAILED ✗'}")
    print("=" * 62)

    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
