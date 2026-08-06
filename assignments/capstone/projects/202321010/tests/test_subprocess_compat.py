"""Tests for Windows-safe subprocess text decoding."""

from docs_code_drift_detector.subprocess_compat import ENCODING_KWARGS, run_text


def test_run_text_uses_utf8_encoding():
    assert ENCODING_KWARGS == {"encoding": "utf-8", "errors": "replace"}
    result = run_text(
        ["python", "-c", "print('ok')"],
        capture_output=True,
        timeout=10,
    )
    assert result.returncode == 0
    assert "ok" in result.stdout
