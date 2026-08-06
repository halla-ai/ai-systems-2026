"""Print UTF-8 file head for Windows terminal demo (avoids PowerShell encoding issues)."""
from __future__ import annotations

import json
import sys
from pathlib import Path


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: python present_show.py <file> [max_lines]", file=sys.stderr)
        return 1
    path = Path(sys.argv[1])
    max_lines = int(sys.argv[2]) if len(sys.argv) > 2 else 30
    if not path.exists():
        print(f"File not found: {path}", file=sys.stderr)
        return 1
    text = path.read_text(encoding="utf-8")
    if path.suffix == ".json" and "drift_report" in path.name:
        data = json.loads(text)
        print(f"drift_count: {data.get('drift_count', len(data.get('drifts', [])))}")
        print(f"functions_scanned: {data.get('functions_scanned')}")
        return 0
    for line in text.splitlines()[:max_lines]:
        print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
