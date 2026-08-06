#!/usr/bin/env python3
"""
log_analyzer.py

A simple harness log analyzer for Lab 06 assignments.

This script reads a harness log file and categorizes error
messages into one of several predefined categories.  The categories
used in this example are:

* syntax  – errors related to syntax (SyntaxError, IndentationError)
* logic   – errors where the program ran but produced wrong results
* timeout – errors indicating that execution timed out
* api     – errors related to API calls or network failures
* other   – any message that does not match the above patterns

The script produces a summary report printed to standard output and
optionally writes the raw categorized results to a JSON file.

Usage:

    python log_analyzer.py path/to/harness.log [--json-output output.json]

This file is a skeleton; feel free to extend it for your own needs.
"""

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, List


def categorize_line(line: str) -> str:
    """
    Categorize a single line of log output.

    Parameters
    ----------
    line : str
        A single line from the harness log.

    Returns
    -------
    str
        The category of the error.  Defaults to 'other'.
    """
    # Lowercase the line for easier matching
    text = line.lower()
    if "syntaxerror" in text or "indentationerror" in text:
        return "syntax"
    if "assertion failed" in text or ("expected" in text and "got" in text):
        return "logic"
    if "timeout" in text or "timed out" in text:
        return "timeout"
    if "connection error" in text or "api" in text:
        return "api"
    return "other"


def analyze_log(filepath: Path) -> Dict[str, List[str]]:
    """
    Analyze the log file and group lines by category.

    Parameters
    ----------
    filepath : pathlib.Path
        The path to the harness log file.

    Returns
    -------
    Dict[str, List[str]]
        A mapping from category name to list of lines in that category.
    """
    categories = defaultdict(list)
    with filepath.open(encoding="utf-8") as f:
        for line in f:
            category = categorize_line(line)
            categories[category].append(line.rstrip())
    return categories


def print_report(categories: Dict[str, List[str]]) -> None:
    """
    Print a summary report of categorized log lines.

    Parameters
    ----------
    categories : Dict[str, List[str]]
        The categorized log lines.
    """
    counts = Counter({k: len(v) for k, v in categories.items()})
    total = sum(counts.values())
    print(f"\nLog analysis summary (total {total} messages):\n")
    for category, count in counts.most_common():
        print(f"  {category:<7} : {count:>5}")

    print("\nSample messages per category:")
    for category, lines in categories.items():
        if not lines:
            continue
        print(f"\n## {category.capitalize()} ({len(lines)} messages)")
        # Show up to 3 sample messages for each category
        for sample in lines[:3]:
            print(f"- {sample}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze harness.log for Lab 06.")
    parser.add_argument(
        "logfile",
        type=Path,
        help="Path to the harness log file to analyze",
    )
    parser.add_argument(
        "--json-output",
        type=Path,
        help="Optional path to write JSON with categorized messages",
    )
    args = parser.parse_args()

    if not args.logfile.exists():
        raise FileNotFoundError(f"Log file {args.logfile} does not exist.")

    categories = analyze_log(args.logfile)
    print_report(categories)

    if args.json_output:
        # Convert default dict to normal dict for JSON serialization
        data = {k: v for k, v in categories.items()}
        with args.json_output.open("w", encoding="utf-8") as out_file:
            json.dump(data, out_file, indent=2, ensure_ascii=False)
        print(f"\nCategorized results written to {args.json_output}")


if __name__ == "__main__":
    main()
