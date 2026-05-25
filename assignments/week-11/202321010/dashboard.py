"""
dashboard.py — .events.jsonl 에서 집계 후 4개 패널 대시보드 생성
  Panel ①  Task Duration by Agent Role   (bar)
  Panel ②  Tool Call Frequency           (donut)
  Panel ③  Gate Pass / Fail Count        (horizontal bar)
  Panel ④  Cumulative Cost per Task      (area-line)
추가로 dashboard_data.csv 출력
"""

import json
import glob
import csv
import sys
from collections import defaultdict
from datetime import datetime

import matplotlib
matplotlib.use("Agg")                        # GUI 없이 파일 저장
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import numpy as np


# ── 팔레트 ────────────────────────────────────────────────────────────────────
COLORS_ROLE = ["#4C72B0", "#DD8452", "#55A868", "#C44E52", "#8172B3"]
COLORS_TOOL = ["#64B5F6", "#81C784", "#FFB74D", "#F06292", "#BA68C8"]
GATE_COLORS = {"pass": "#43A047", "fail": "#E53935"}
COST_COLOR  = "#1565C0"
BG_COLOR    = "#FAFAFA"


def parse_ts(ts: str) -> datetime:
    return datetime.fromisoformat(ts)


def load_events(path: str) -> list:
    events = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                events.append(json.loads(line))
    return events


def aggregate(events: list) -> dict:
    """이벤트 목록에서 대시보드용 집계 데이터 추출"""
    task_roles    = {}          # tid → role
    task_costs    = defaultdict(float)
    task_start    = {}          # tid → ts
    task_end      = {}          # tid → ts
    tool_counts   = defaultdict(int)
    gate_counts   = defaultdict(int)
    cum_cost_seq  = []          # (task_id, cumulative_cost)

    for ev in events:
        etype = ev["event_type"]
        tid   = ev.get("task_id")

        if etype == "task.start":
            task_roles[tid] = ev.get("agent_role", "unknown")
            task_start[tid] = ev.get("timestamp")

        elif etype in ("step.reason", "tool.call"):
            cost = ev.get("cost", 0.0)
            if tid:
                task_costs[tid] += cost
            if etype == "tool.call":
                tool_counts[ev.get("tool_name", "unknown")] += 1

        elif etype == "gate.check":
            gate_counts[ev.get("gate_result", "unknown")] += 1

        elif etype == "task.end":
            if tid:
                task_end[tid] = ev.get("timestamp")

    # 태스크 순서 보존
    task_order = list(task_roles.keys())

    # duration 계산
    task_durations = {}
    for tid in task_order:
        try:
            s = parse_ts(task_start[tid])
            e = parse_ts(task_end[tid])
            task_durations[tid] = round((e - s).total_seconds(), 3)
        except Exception:
            task_durations[tid] = 0.0

    # 누적 비용 시퀀스
    cumulative = 0.0
    for tid in task_order:
        cumulative += task_costs[tid]
        cum_cost_seq.append((tid, round(cumulative, 8)))

    return {
        "task_order":     task_order,
        "task_roles":     task_roles,
        "task_costs":     task_costs,
        "task_durations": task_durations,
        "tool_counts":    dict(tool_counts),
        "gate_counts":    dict(gate_counts),
        "cum_cost_seq":   cum_cost_seq,
    }


def save_csv(agg: dict, path: str = "dashboard_data.csv"):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["task_id", "agent_role", "duration_s",
                    "cost_usd", "cumulative_cost_usd"])
        cumulative = 0.0
        for tid in agg["task_order"]:
            role = agg["task_roles"].get(tid, "")
            dur  = agg["task_durations"].get(tid, 0.0)
            cost = agg["task_costs"].get(tid, 0.0)
            cumulative += cost
            w.writerow([tid, role, f"{dur:.4f}",
                        f"{cost:.8f}", f"{cumulative:.8f}"])
    print(f"[✓] CSV data    : {path}")


def plot_dashboard(agg: dict, out_png: str = "dashboard.png"):
    fig = plt.figure(figsize=(16, 11), facecolor=BG_COLOR)
    fig.suptitle(
        "Lab 11 - Agent OS Runtime Dashboard\n"
        "OpenTelemetry RALPH Loop Metrics",
        fontsize=15, fontweight="bold", y=0.98,
    )
    gs = gridspec.GridSpec(2, 2, figure=fig, hspace=0.48, wspace=0.38)

    task_order = agg["task_order"]
    roles      = [agg["task_roles"].get(t, "?")      for t in task_order]
    durs       = [agg["task_durations"].get(t, 0.0)  for t in task_order]
    costs      = [float(agg["task_costs"].get(t, 0.0)) * 1_000_000 for t in task_order]  # μUSD

    # ── Panel ① Task Duration by Agent Role ─────────────────────────────────
    ax1 = fig.add_subplot(gs[0, 0])
    ax1.set_facecolor(BG_COLOR)
    bars = ax1.bar(roles, durs,
                   color=COLORS_ROLE[:len(roles)],
                   edgecolor="white", linewidth=0.8, zorder=3)
    ax1.bar_label(bars, fmt="%.3fs", fontsize=8, padding=3, color="#333")
    ax1.set_title("① Task Duration by Agent Role", fontweight="bold", fontsize=11)
    ax1.set_xlabel("Agent Role", fontsize=9)
    ax1.set_ylabel("Duration (s)", fontsize=9)
    ax1.set_ylim(0, max(durs) * 1.28 if durs else 1)
    ax1.grid(axis="y", linestyle="--", alpha=0.4, zorder=0)
    ax1.spines[["top", "right"]].set_visible(False)
    ax1.tick_params(axis="x", labelsize=8)

    # ── Panel ② Tool Call Frequency ─────────────────────────────────────────
    ax2 = fig.add_subplot(gs[0, 1])
    ax2.set_facecolor(BG_COLOR)
    tc   = agg["tool_counts"]
    if tc:
        tools  = list(tc.keys())
        counts = [tc[t] for t in tools]
        wedge_props = dict(width=0.48, edgecolor="white", linewidth=1.2)
        ax2.pie(
            counts, labels=tools, autopct="%1.0f%%",
            startangle=90,
            colors=COLORS_TOOL[:len(tools)],
            wedgeprops=wedge_props,
            textprops={"fontsize": 8},
            pctdistance=0.75,
        )
    ax2.set_title("② Tool Call Frequency", fontweight="bold", fontsize=11)

    # ── Panel ③ Gate Pass / Fail ─────────────────────────────────────────────
    ax3 = fig.add_subplot(gs[1, 0])
    ax3.set_facecolor(BG_COLOR)
    gc = agg["gate_counts"]
    if gc:
        labels = list(gc.keys())
        vals   = [gc[l] for l in labels]
        cols   = [GATE_COLORS.get(l, "#90A4AE") for l in labels]
        hbars  = ax3.barh(labels, vals, color=cols,
                          edgecolor="white", linewidth=0.8, height=0.5, zorder=3)
        ax3.bar_label(hbars, fontsize=10, padding=4, color="#333")
        ax3.set_xlim(0, max(vals) * 1.4 if vals else 1)
    ax3.set_title("③ Gate Pass / Fail Count", fontweight="bold", fontsize=11)
    ax3.set_xlabel("Count", fontsize=9)
    ax3.grid(axis="x", linestyle="--", alpha=0.4, zorder=0)
    ax3.spines[["top", "right"]].set_visible(False)

    # ── Panel ④ Cumulative Cost per Task ─────────────────────────────────────
    ax4 = fig.add_subplot(gs[1, 1])
    ax4.set_facecolor(BG_COLOR)
    cum_seq = agg["cum_cost_seq"]
    if cum_seq:
        x_labels = [s[0] for s in cum_seq]
        y_vals   = [s[1] * 1_000_000 for s in cum_seq]   # μUSD
        x_idx    = list(range(len(x_labels)))
        ax4.fill_between(x_idx, y_vals, alpha=0.15, color=COST_COLOR)
        ax4.plot(x_idx, y_vals, "o-", color=COST_COLOR,
                 linewidth=2.2, markersize=7, zorder=3)
        for xi, yi in zip(x_idx, y_vals):
            ax4.annotate(f"{yi:.1f}", (xi, yi),
                         textcoords="offset points", xytext=(0, 8),
                         ha="center", fontsize=8, color=COST_COLOR)
        ax4.set_xticks(x_idx)
        ax4.set_xticklabels(x_labels, rotation=15, fontsize=8)
        ax4.set_ylim(0, max(y_vals) * 1.3 if y_vals else 1)
    ax4.set_title("④ Cumulative Cost per Task  (μ$)", fontweight="bold", fontsize=11)
    ax4.set_xlabel("Task ID", fontsize=9)
    ax4.set_ylabel("Cumulative Cost (μUSD)", fontsize=9)
    ax4.grid(axis="y", linestyle="--", alpha=0.4, zorder=0)
    ax4.spines[["top", "right"]].set_visible(False)

    plt.savefig(out_png, dpi=150, bbox_inches="tight",
                facecolor=BG_COLOR, edgecolor="none")
    plt.close()
    print(f"[✓] Dashboard   : {out_png}  (4 panels)")


def build_dashboard(events_file: str):
    events = load_events(events_file)
    agg    = aggregate(events)
    save_csv(agg)
    plot_dashboard(agg)


if __name__ == "__main__":
    files = sorted(glob.glob("*.events.jsonl"))
    if not files:
        print("No .events.jsonl found. Run agent_harness.py first.")
        sys.exit(1)
    build_dashboard(files[-1])
