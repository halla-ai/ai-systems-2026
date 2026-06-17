"""Subprocess helpers safe on Windows (avoids cp949 UnicodeDecodeError)."""

from __future__ import annotations

import subprocess
from typing import Any

ENCODING_KWARGS: dict[str, Any] = {"encoding": "utf-8", "errors": "replace"}


def run_text(
    args: list[str] | tuple[str, ...],
    *,
    check: bool = False,
    capture_output: bool = False,
    timeout: float | None = None,
    cwd: str | None = None,
    **kwargs: Any,
) -> subprocess.CompletedProcess[str]:
    """Run subprocess with UTF-8 text mode (not locale cp949 on Windows)."""
    return subprocess.run(
        args,
        check=check,
        capture_output=capture_output,
        text=True,
        timeout=timeout,
        cwd=cwd,
        **ENCODING_KWARGS,
        **kwargs,
    )
