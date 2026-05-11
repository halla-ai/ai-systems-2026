"""
benchmark.py - Commercial vs Open-Weight Model Benchmark (Lab 10)

Compares GPT-4o-mini (commercial) vs Qwen2.5-7B-Instruct (open-weight)
across 5 identical tasks and reports:
  - Average latency (s)
  - Throughput (tokens/sec)
  - Failure rate (%)
  - Estimated cost (USD or local GPU cost)

Usage
-----
# Both models (default)
python benchmark.py

# Only the local vLLM model (no OpenAI key needed)
python benchmark.py --model qwen

# Only the commercial model
python benchmark.py --model gpt-mini

Environment variables
---------------------
OPENAI_API_KEY  – required for GPT-4o-mini
VLLM_BASE_URL   – vLLM endpoint   (default: http://localhost:8000/v1)
VLLM_API_KEY    – vLLM API key    (default: test-key)
"""

from __future__ import annotations

import argparse
import csv
import os
import statistics
import time
from dataclasses import dataclass, field, asdict
from typing import Optional

from openai import OpenAI, OpenAIError

from adapter import get_client, get_model

# ---------------------------------------------------------------------------
# Pricing (as of 2025-05)
# ---------------------------------------------------------------------------

# GPT-4o-mini  —  https://openai.com/pricing
GPT4O_MINI_INPUT_USD_PER_1M  = 0.15   # $0.15 / 1M prompt tokens
GPT4O_MINI_OUTPUT_USD_PER_1M = 0.60   # $0.60 / 1M completion tokens

# Qwen2.5-7B-Instruct  —  local GPU (RTX 4090 / A100)
# A100 80 GB ≈ $2.00 / hr on Lambda Cloud
# RTX 4090: 450 W × 150 KRW/kWh ≈ 0.068 KRW/s → use A100 cloud as reference
A100_USD_PER_HOUR = 2.00               # cloud A100

# ---------------------------------------------------------------------------
# Tasks
# ---------------------------------------------------------------------------

TASKS: list[dict] = [
    {
        "id": 1,
        "name": "Summarization",
        "prompt": "Summarize the concept of transformer neural networks in 3 sentences.",
    },
    {
        "id": 2,
        "name": "Code Generation",
        "prompt": "Write a Python REST API endpoint using FastAPI that returns a list of users.",
    },
    {
        "id": 3,
        "name": "Translation",
        "prompt": "Translate the following sentence into Korean: 'Artificial intelligence is transforming every industry.'",
    },
    {
        "id": 4,
        "name": "Math Explanation",
        "prompt": "Explain gradient descent in simple terms that a high-school student can understand.",
    },
    {
        "id": 5,
        "name": "Business E-mail",
        "prompt": "Write a polite business email to request a project status meeting next Monday.",
    },
]

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class TaskResult:
    model_alias:        str
    model_name:         str
    task_id:            int
    task_name:          str
    status:             str          # "success" | "fail"
    latency_s:          float = 0.0
    prompt_tokens:      int   = 0
    completion_tokens:  int   = 0
    total_tokens:       int   = 0
    tokens_per_sec:     float = 0.0
    cost_usd:           float = 0.0
    error:              str   = ""
    response_snippet:   str   = ""


# ---------------------------------------------------------------------------
# Cost helpers
# ---------------------------------------------------------------------------

def estimate_cost_gpt(prompt_tok: int, completion_tok: int) -> float:
    return (
        prompt_tok     * GPT4O_MINI_INPUT_USD_PER_1M  / 1_000_000
        + completion_tok * GPT4O_MINI_OUTPUT_USD_PER_1M / 1_000_000
    )


def estimate_cost_local(latency_s: float) -> float:
    """Estimate cost using A100 cloud pricing as a proxy for any local GPU."""
    return latency_s / 3600 * A100_USD_PER_HOUR


# ---------------------------------------------------------------------------
# Core benchmark logic
# ---------------------------------------------------------------------------

def run_model(alias: str, max_tokens: int = 250, repeat: int = 1) -> list[TaskResult]:
    """Run all TASKS for the given model alias and return results."""
    try:
        client, model_name = get_client(alias)
    except ValueError as exc:
        print(f"[ERROR] {exc}")
        return []

    print(f"\n{'='*62}")
    print(f"  Model alias : {alias}")
    print(f"  Model name  : {model_name}")
    print(f"  Max tokens  : {max_tokens}   Repeat : {repeat}")
    print(f"{'='*62}")

    results: list[TaskResult] = []

    for task in TASKS:
        for _ in range(repeat):
            result = TaskResult(
                model_alias=alias,
                model_name=model_name,
                task_id=task["id"],
                task_name=task["name"],
                status="fail",
            )

            start = time.perf_counter()
            try:
                response = client.chat.completions.create(
                    model=model_name,
                    messages=[{"role": "user", "content": task["prompt"]}],
                    max_tokens=max_tokens,
                    temperature=0.7,
                )
                latency = time.perf_counter() - start

                usage = response.usage
                content = response.choices[0].message.content or ""

                result.status            = "success"
                result.latency_s         = round(latency, 4)
                result.prompt_tokens     = usage.prompt_tokens
                result.completion_tokens = usage.completion_tokens
                result.total_tokens      = usage.total_tokens
                result.tokens_per_sec    = round(usage.total_tokens / latency, 2) if latency > 0 else 0.0
                result.response_snippet  = content[:120].replace("\n", " ")

                if alias in ("gpt-mini", "gpt4o-mini"):
                    result.cost_usd = estimate_cost_gpt(usage.prompt_tokens, usage.completion_tokens)
                else:
                    result.cost_usd = estimate_cost_local(latency)

            except OpenAIError as exc:
                latency = time.perf_counter() - start
                result.latency_s = round(latency, 4)
                result.error     = str(exc)[:200]
                print(f"  [FAIL] Task {task['id']} ({task['name']}): {result.error}")

            results.append(result)

            status_tag = "OK" if result.status == "success" else "FAIL"
            print(
                f"  [{status_tag}] Task {task['id']:2d} {task['name']:<22s} "
                f"latency={result.latency_s:.3f}s  "
                f"tok/s={result.tokens_per_sec:.1f}  "
                f"cost=${result.cost_usd:.6f}"
            )

    return results


# ---------------------------------------------------------------------------
# Aggregation & reporting
# ---------------------------------------------------------------------------

def aggregate(results: list[TaskResult]) -> dict:
    successes = [r for r in results if r.status == "success"]
    failures  = [r for r in results if r.status == "fail"]

    n_total    = len(results)
    n_success  = len(successes)
    n_fail     = len(failures)
    fail_rate  = n_fail / n_total * 100 if n_total else 0.0

    latencies    = [r.latency_s      for r in successes]
    tps_list     = [r.tokens_per_sec for r in successes]
    cost_list    = [r.cost_usd       for r in successes]

    avg_latency  = round(statistics.mean(latencies),    4) if latencies else 0.0
    avg_tps      = round(statistics.mean(tps_list),     2) if tps_list  else 0.0
    total_cost   = round(sum(cost_list),                6)

    return {
        "n_total":    n_total,
        "n_success":  n_success,
        "n_fail":     n_fail,
        "fail_rate":  round(fail_rate, 1),
        "avg_latency_s":  avg_latency,
        "avg_tokens_per_sec": avg_tps,
        "total_cost_usd": total_cost,
    }


def print_summary_table(summaries: dict[str, dict]) -> None:
    header = f"{'Model':<20s} {'Avg Lat(s)':>10} {'Tok/s':>8} {'Fail%':>7} {'Total Cost(USD)':>16}"
    print(f"\n{'='*65}")
    print("  BENCHMARK SUMMARY")
    print(f"{'='*65}")
    print(header)
    print("-" * 65)
    for alias, s in summaries.items():
        print(
            f"  {alias:<18s} {s['avg_latency_s']:>10.3f} "
            f"{s['avg_tokens_per_sec']:>8.1f} "
            f"{s['fail_rate']:>6.1f}% "
            f"  ${s['total_cost_usd']:>13.6f}"
        )
    print("=" * 65)


def save_csv(all_results: list[TaskResult], path: str = "results.csv") -> None:
    if not all_results:
        return
    fieldnames = list(asdict(all_results[0]).keys())
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in all_results:
            writer.writerow(asdict(r))
    print(f"\n[Saved] {path}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Lab 10 vLLM Benchmark")
    parser.add_argument(
        "--model",
        choices=["qwen", "gpt-mini", "both"],
        default="both",
        help="Which model(s) to benchmark (default: both)",
    )
    parser.add_argument("--max-tokens", type=int, default=250)
    parser.add_argument("--repeat",     type=int, default=1,
                        help="Repeat each task N times (for stable averages)")
    parser.add_argument("--csv", default="results.csv")
    args = parser.parse_args()

    aliases: list[str]
    if args.model == "both":
        aliases = ["qwen", "gpt-mini"]
    else:
        aliases = [args.model]

    all_results: list[TaskResult] = []
    summaries:   dict[str, dict]  = {}

    for alias in aliases:
        results = run_model(alias, max_tokens=args.max_tokens, repeat=args.repeat)
        all_results.extend(results)
        if results:
            summaries[alias] = aggregate(results)

    if summaries:
        print_summary_table(summaries)

    save_csv(all_results, path=args.csv)


if __name__ == "__main__":
    main()
