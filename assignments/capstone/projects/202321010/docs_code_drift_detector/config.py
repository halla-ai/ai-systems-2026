"""Runtime configuration (env-based)."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass
class AppConfig:
    use_llm: bool = False
    detect_semantic: bool = False
    llm_model: str = "gpt-4o-mini"
    openai_api_key: str | None = None
    create_pr: bool = False
    dry_run_pr: bool = False
    hotl_approved: bool = False
    wait_hotl: bool = False
    wait_hotl_timeout_sec: float = 300.0
    wait_hotl_poll_sec: float = 2.0
    max_qa_iterations: int = 5
    max_hotl_cycles: int = 5
    gh_available: bool = False
    base_branch: str = "main"
    cost_budget_usd: float = 0.50
    latency_budget_sec: float = 120.0

    @classmethod
    def from_env(
        cls,
        *,
        use_llm: bool = False,
        detect_semantic: bool = False,
        create_pr: bool = False,
        dry_run_pr: bool = False,
        hotl_approved: bool = False,
        wait_hotl: bool = False,
        wait_hotl_timeout_sec: float = 300.0,
        wait_hotl_poll_sec: float = 2.0,
        max_qa_iterations: int = 5,
        max_hotl_cycles: int = 5,
    ) -> AppConfig:
        api_key = os.getenv("OPENAI_API_KEY") or os.getenv("DRIFT_OPENAI_API_KEY")
        gh = os.getenv("GH_TOKEN") or os.getenv("GITHUB_TOKEN")
        return cls(
            use_llm=use_llm or os.getenv("DRIFT_USE_LLM", "").lower() in ("1", "true", "yes"),
            detect_semantic=detect_semantic or os.getenv("DRIFT_DETECT_SEMANTIC", "").lower() in ("1", "true", "yes"),
            llm_model=os.getenv("DRIFT_LLM_MODEL", "gpt-4o-mini"),
            openai_api_key=api_key,
            create_pr=create_pr or os.getenv("DRIFT_CREATE_PR", "").lower() in ("1", "true", "yes"),
            dry_run_pr=dry_run_pr,
            hotl_approved=hotl_approved,
            wait_hotl=wait_hotl or os.getenv("DRIFT_WAIT_HOTL", "").lower() in ("1", "true", "yes"),
            wait_hotl_timeout_sec=float(os.getenv("DRIFT_WAIT_HOTL_TIMEOUT_SEC", str(wait_hotl_timeout_sec))),
            wait_hotl_poll_sec=float(os.getenv("DRIFT_WAIT_HOTL_POLL_SEC", str(wait_hotl_poll_sec))),
            max_qa_iterations=max_qa_iterations,
            max_hotl_cycles=max_hotl_cycles,
            gh_available=bool(gh) or _gh_cli_authenticated(),
            base_branch=os.getenv("DRIFT_BASE_BRANCH", "main"),
            cost_budget_usd=float(os.getenv("DRIFT_COST_BUDGET_USD", "0.50")),
            latency_budget_sec=float(os.getenv("DRIFT_LATENCY_BUDGET_SEC", "120")),
        )


def _gh_cli_authenticated() -> bool:
    import shutil
    import subprocess

    if not shutil.which("gh"):
        return False
    try:
        from docs_code_drift_detector.subprocess_compat import run_text

        result = run_text(
            ["gh", "auth", "status"],
            capture_output=True,
            timeout=10,
        )
        return result.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False
