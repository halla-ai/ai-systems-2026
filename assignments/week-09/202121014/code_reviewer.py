from __future__ import annotations

import json
import os
import re
import subprocess
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ReviewResult:
    severity: str
    issues: list[str]
    suggestions: list[str]
    score: int

    def should_block(self) -> bool:
        return self.severity == "block"


class CodeReviewer:
    def __init__(self, workdir: Path | str | None = None) -> None:
        self.workdir = Path(workdir or Path(__file__).resolve().parent)

    def get_diff(self) -> str:
        commands = [
            ["git", "diff", "HEAD", "--", "."],
            ["git", "diff", "--", "."],
        ]
        for command in commands:
            try:
                completed = subprocess.run(
                    command,
                    cwd=self.workdir,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    check=False,
                )
            except OSError:
                continue
            diff = completed.stdout.strip()
            if diff:
                return diff
        return ""

    def review_diff(self, diff: str) -> ReviewResult:
        if not diff.strip():
            return ReviewResult(severity="pass", issues=[], suggestions=[], score=100)

        try:
            api_key = os.getenv("ANTHROPIC_API_KEY")
            if api_key:
                reviewed = self._review_with_anthropic(diff=diff, api_key=api_key)
                if reviewed is not None:
                    return reviewed
        except Exception:
            pass

        return self._fallback_review(diff)

    def _review_with_anthropic(self, diff: str, api_key: str) -> ReviewResult | None:
        prompt = (
            "Review this git diff and respond with JSON containing severity, issues, suggestions, and score. "
            "Severity must be one of pass, warn, block.\n\n"
            f"{diff[:12000]}"
        )
        payload = json.dumps(
            {
                "model": "claude-3-5-haiku-latest",
                "max_tokens": 400,
                "messages": [{"role": "user", "content": prompt}],
            }
        ).encode("utf-8")

        request = urllib.request.Request(
            url="https://api.anthropic.com/v1/messages",
            data=payload,
            headers={
                "content-type": "application/json",
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                body = response.read().decode("utf-8")
        except (urllib.error.URLError, TimeoutError):
            return None

        try:
            response_json = json.loads(body)
            content = response_json["content"][0]["text"]
            parsed = json.loads(content)
        except (KeyError, IndexError, TypeError, json.JSONDecodeError):
            return None

        severity = str(parsed.get("severity", "warn"))
        issues = [str(item) for item in parsed.get("issues", [])]
        suggestions = [str(item) for item in parsed.get("suggestions", [])]
        score = int(parsed.get("score", 50))
        return ReviewResult(severity=severity, issues=issues, suggestions=suggestions, score=max(0, min(score, 100)))

    def _fallback_review(self, diff: str) -> ReviewResult:
        added_lines = [
            line[1:]
            for line in diff.splitlines()
            if line.startswith("+") and not line.startswith("+++")
        ]
        joined = "\n".join(added_lines)

        issues: list[str] = []
        suggestions: list[str] = []
        block_hits = []
        warn_hits = []

        danger_patterns = {
            r"\beval\s*\(": "Avoid `eval()` in production code.",
            r"\bexec\s*\(": "Avoid `exec()` in production code.",
            r"\bos\.system\s*\(": "Avoid `os.system()` and prefer safer subprocess APIs.",
            r"\bshell\s*=\s*True\b": "Avoid `subprocess` with `shell=True` unless strictly required.",
        }
        warn_patterns = {
            r"\bTODO\b": "Remove TODO markers or resolve the unfinished logic.",
            r"^\s*pass\s*$": "Replace placeholder `pass` statements with real behavior.",
            r"\bprint\s*\(": "Remove debug `print()` calls before approval.",
            r"^\s*except\s*:\s*$": "Avoid bare `except:` blocks and catch explicit exceptions.",
        }

        for pattern, message in danger_patterns.items():
            if re.search(pattern, joined, re.IGNORECASE | re.MULTILINE):
                block_hits.append(message)

        for pattern, message in warn_patterns.items():
            if re.search(pattern, joined, re.IGNORECASE | re.MULTILINE):
                warn_hits.append(message)

        if block_hits:
            issues.extend(block_hits)
            suggestions.append("Remove or refactor the blocked patterns before merging.")
            score = max(0, 100 - 70 - (10 * len(warn_hits)))
            return ReviewResult(severity="block", issues=issues, suggestions=suggestions, score=score)

        if warn_hits:
            issues.extend(warn_hits)
            suggestions.append("Clean up the warning-level issues to improve code quality.")
            score = max(40, 100 - (10 * len(warn_hits)))
            return ReviewResult(severity="warn", issues=issues, suggestions=suggestions, score=score)

        return ReviewResult(
            severity="pass",
            issues=[],
            suggestions=["No blocking issues detected by the fallback reviewer."],
            score=100,
        )

