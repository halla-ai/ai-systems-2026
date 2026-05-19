#!/usr/bin/env python3
"""
ab_test.py

Automate A/B testing for different prompt versions in Lab 06.

This script provides a simple framework to execute two different prompts
(`prompt_v1.md` and `prompt_v2.md`) against your agent or application, collect
metrics such as success/failure, number of iterations, and execution time, and
store the results as JSON.

Usage:

    python ab_test.py --run-count 5 --output results.json

You will need to implement the `run_prompt` function to integrate with your
agent or application.  The provided skeleton uses placeholders to indicate
where your code should go.
"""

import argparse
import json
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import List


@dataclass
class RunResult:
    variant: str  # "v1" or "v2"
    success: bool
    iterations: int
    elapsed_seconds: float


def run_prompt(variant: str) -> RunResult:
    """
    Execute the agent with the specified prompt variant.

    Parameters
    ----------
    variant : str
        Either "v1" or "v2" to indicate which prompt file to use.

    Returns
    -------
    RunResult
        A dataclass instance summarizing the run.

    Note
    ----
    This function must be customized to integrate with your agent or
    application.  Replace the placeholder logic with actual execution steps.
    """
    # Record start time
    start = time.perf_counter()

    # TODO: Replace the following placeholder with real execution logic.
    # For demonstration purposes, we'll simulate a success for v2 and a failure for v1.
    if variant == "v2":
        success = True
        iterations = 1
    else:
        success = False
        iterations = 2

    # Simulate some processing time
    time.sleep(0.5)
    end = time.perf_counter()
    elapsed = end - start

    return RunResult(variant=variant, success=success, iterations=iterations, elapsed_seconds=elapsed)


def run_ab_test(run_count: int) -> List[RunResult]:
    """
    Run A/B tests for both prompts a specified number of times.

    Parameters
    ----------
    run_count : int
        Number of runs to perform for each variant.

    Returns
    -------
    List[RunResult]
        A list of RunResult instances.
    """
    results: List[RunResult] = []
    for _ in range(run_count):
        for variant in ("v1", "v2"):
            result = run_prompt(variant)
            results.append(result)
    return results


def write_results(results: List[RunResult], output_path: Path) -> None:
    """
    Write A/B test results to a JSON file.

    Parameters
    ----------
    results : List[RunResult]
        The list of run results.
    output_path : pathlib.Path
        Filepath to write the JSON data.
    """
    data = [asdict(result) for result in results]
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"Wrote A/B results to {output_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run A/B tests for prompt variants.")
    parser.add_argument(
        "--run-count",
        type=int,
        default=3,
        help="Number of times to run each prompt variant (default: 3)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("ab_results.json"),
        help="Path to write the JSON results (default: ab_results.json)",
    )
    args = parser.parse_args()

    results = run_ab_test(args.run_count)
    write_results(results, args.output)


if __name__ == "__main__":
    main()
