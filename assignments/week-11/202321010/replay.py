"""
replay.py — .events.jsonl에서 output, cost, closed 상태를 재계산하여
replay_snapshot.json 생성
"""

import json
import glob
import sys
from datetime import datetime


def replay(events_file: str, out_file: str = "replay_snapshot.json") -> dict:
    # ── 이벤트 로드 ──────────────────────────────────────────────────────────────
    events = []
    with open(events_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                events.append(json.loads(line))

    # ── 재계산 상태 변수 ──────────────────────────────────────────────────────────
    run_id        = None
    run_closed    = False
    run_start_ts  = None
    run_end_ts    = None
    total_cost    = 0.0

    tasks         = {}   # task_id → dict
    task_order    = []   # 순서 보존
    artifacts     = []

    for ev in events:
        etype = ev["event_type"]
        ts    = ev.get("timestamp")

        # run 이벤트
        if etype == "run.start":
            run_id       = ev.get("run_id")
            run_start_ts = ts

        elif etype == "run.end":
            run_closed   = ev.get("closed", False)
            run_end_ts   = ts

        # task 이벤트
        elif etype == "task.start":
            tid = ev["task_id"]
            task_order.append(tid)
            tasks[tid] = {
                "task_id":     tid,
                "agent_role":  ev.get("agent_role"),
                "model":       ev.get("model"),
                "description": ev.get("description"),
                "start_ts":    ts,
                "end_ts":      None,
                "cost":        0.0,
                "output":      None,
                "gate_result": None,
                "artifact_path": None,
                "closed":      False,
            }

        elif etype in ("step.reason", "tool.call"):
            tid  = ev.get("task_id")
            cost = ev.get("cost", 0.0)
            total_cost += cost
            if tid and tid in tasks:
                tasks[tid]["cost"] += cost
            if etype == "tool.call" and tid in tasks:
                tasks[tid]["output"] = ev.get("result")

        elif etype == "gate.check":
            tid = ev.get("task_id")
            if tid and tid in tasks:
                tasks[tid]["gate_result"] = ev.get("gate_result")

        elif etype == "artifact.save":
            path = ev.get("artifact_path")
            tid  = ev.get("task_id")
            if path:
                artifacts.append(path)
            if tid and tid in tasks:
                tasks[tid]["artifact_path"] = path
                # output 객체가 있으면 덮어쓰기
                if ev.get("output"):
                    tasks[tid]["output"] = ev["output"]

        elif etype == "task.end":
            tid = ev.get("task_id")
            if tid and tid in tasks:
                tasks[tid]["end_ts"]      = ts
                tasks[tid]["closed"]      = ev.get("closed", False)
                tasks[tid]["gate_result"] = ev.get("gate_result",
                                                   tasks[tid]["gate_result"])

    # ── 태스크 duration 계산 ──────────────────────────────────────────────────────
    for t in tasks.values():
        try:
            s = datetime.fromisoformat(t["start_ts"])
            e = datetime.fromisoformat(t["end_ts"])
            t["duration_s"] = round((e - s).total_seconds(), 4)
        except Exception:
            t["duration_s"] = None

    # ── 스냅샷 조립 ───────────────────────────────────────────────────────────────
    task_list = [tasks[tid] for tid in task_order if tid in tasks]

    snapshot = {
        "meta": {
            "schema_version":     "1.0",
            "generated_by":       "replay.py",
            "source_events_file": events_file,
            "total_events":       len(events),
        },
        "run": {
            "run_id":       run_id,
            "start_ts":     run_start_ts,
            "end_ts":       run_end_ts,
            "closed":       run_closed,
            "total_cost_usd": round(total_cost, 8),
        },
        "summary": {
            "tasks_total":       len(task_list),
            "tasks_closed":      sum(1 for t in task_list if t["closed"]),
            "tasks_gate_pass":   sum(1 for t in task_list if t.get("gate_result") == "pass"),
            "tasks_gate_fail":   sum(1 for t in task_list if t.get("gate_result") == "fail"),
            "total_artifacts":   len(artifacts),
        },
        "tasks":     task_list,
        "artifacts": artifacts,
    }

    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(snapshot, f, indent=2, ensure_ascii=False)

    # ── 콘솔 리포트 ───────────────────────────────────────────────────────────────
    r  = snapshot["run"]
    sm = snapshot["summary"]
    print(f"\n{'='*55}")
    print(f"  replay_snapshot.json  ←  {events_file}")
    print(f"{'='*55}")
    print(f"  run_id        : {r['run_id']}")
    print(f"  closed        : {r['closed']}")
    print(f"  total_cost    : ${r['total_cost_usd']:.8f}")
    print(f"  tasks total   : {sm['tasks_total']}")
    print(f"  tasks closed  : {sm['tasks_closed']}")
    print(f"  gate  pass    : {sm['tasks_gate_pass']}")
    print(f"  gate  fail    : {sm['tasks_gate_fail']}")
    print(f"  artifacts     : {sm['total_artifacts']}")
    print(f"{'='*55}\n")
    print(f"[✓] Snapshot    : {out_file}")

    return snapshot


if __name__ == "__main__":
    files = sorted(glob.glob("*.events.jsonl"))
    if not files:
        print("No .events.jsonl found. Run agent_harness.py first.")
        sys.exit(1)
    replay(files[-1])
