"""PR Agent — dry-run and GitHub PR creation (HOTL-gated)."""

from __future__ import annotations

import json
import shutil
from abc import ABC, abstractmethod
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

import subprocess

from docs_code_drift_detector.subprocess_compat import run_text


@dataclass
class PRRequest:
    title: str
    body: str
    patch_path: Path
    base_branch: str = "main"
    head_branch: str = "docs/drift-fix"
    draft: bool = False


@dataclass
class PRResult:
    success: bool
    pr_url: str | None = None
    message: str = ""
    dry_run: bool = False


@dataclass
class DryRunPRContent:
    title: str
    body: str
    base_branch: str
    head_branch: str
    patch_path: Path
    report_path: Path

    def format_output(self) -> str:
        """Format dry-run PR preview for terminal output."""
        lines = [
            "=" * 60,
            "DRY-RUN PR PREVIEW (no gh command executed)",
            "=" * 60,
            "",
            f"Base branch : {self.base_branch}",
            f"Head branch : {self.head_branch}",
            f"Report      : {self.report_path}",
            f"Patch       : {self.patch_path}",
            "",
            "-" * 60,
            "TITLE",
            "-" * 60,
            self.title,
            "",
            "-" * 60,
            "BODY",
            "-" * 60,
            self.body,
            "",
            "=" * 60,
            "Use --create-pr --hotl-approved for real gh pr create",
            "=" * 60,
        ]
        return "\n".join(lines)


class PRAgent(ABC):
    """Abstract interface for creating pull requests from drift fixes."""

    @abstractmethod
    def create_pr(self, request: PRRequest) -> PRResult:
        """Create a pull request with the given patch and metadata."""
        ...


def load_drift_report(report_path: Path) -> dict:
    """Load drift_report.json from disk."""
    return json.loads(report_path.read_text(encoding="utf-8"))


def generate_pr_title(report: dict) -> str:
    """Generate PR title from drift report."""
    drift_count = report.get("drift_count", len(report.get("drifts", [])))
    project_root = Path(report.get("project_root", "project"))
    project_name = project_root.name or "project"
    if drift_count == 0:
        return f"docs: no documentation drift detected in {project_name}"
    return f"docs: fix {drift_count} documentation drift(s) in {project_name}"


def generate_pr_body(report: dict, patch_path: Path) -> str:
    """Generate PR body from drift report."""
    drifts = report.get("drifts", [])
    decisions = report.get("decisions", [])
    suggestions = report.get("code_suggestions", [])
    functions_scanned = report.get("functions_scanned", 0)
    drift_count = report.get("drift_count", len(drifts))

    lines = [
        "## Summary",
        "",
        f"- Functions scanned: **{functions_scanned}**",
        f"- Drifts detected: **{drift_count}**",
        f"- Patch file: `{patch_path.name}`",
        "",
        "> This PR updates **documentation only**. Code changes are suggested as comments, not auto-applied.",
        "",
    ]

    structural = [d for d in drifts if d.get("drift_type") != "semantic_mismatch"]
    semantic = [d for d in drifts if d.get("drift_type") == "semantic_mismatch"]

    if drifts:
        type_counts = Counter(d["drift_type"] for d in drifts)
        lines.extend(["## Drift breakdown", ""])
        for drift_type, count in sorted(type_counts.items()):
            lines.append(f"- `{drift_type}`: {count}")
        lines.append("")

    if semantic:
        lines.extend([
            "## Semantic mismatch candidates (HITL — no auto-fix)",
            "",
            "> LLM-flagged behavioral mismatches. **Not included in patch.diff.** "
            "Human must decide whether to update docs or code.",
            "",
        ])
        for drift in semantic:
            lines.append(
                f"### `{drift['module']}.{drift['function']}` — `semantic_mismatch`"
            )
            lines.append(f"- **Doc claim:** {drift.get('doc_value')}")
            lines.append(f"- **Code behavior:** {drift.get('code_value')}")
            lines.append(f"- **Confidence:** {drift.get('confidence')}")
            evidence = drift.get("evidence", {})
            if evidence.get("reason"):
                lines.append(f"- **Reason:** {evidence.get('reason')}")
            lines.append("")

    if structural:
        lines.extend(["## Structural drifts (auto doc patch)", ""])
        for drift in structural:
            lines.append(
                f"### `{drift['module']}.{drift['function']}` — `{drift['drift_type']}`"
            )
            lines.append(f"- **Doc:** `{drift.get('doc_value')}`")
            lines.append(f"- **Code:** `{drift.get('code_value')}`")
            evidence = drift.get("evidence", {})
            if evidence:
                lines.append(f"- **Evidence:** doc=\"{evidence.get('doc', '')}\", "
                             f"code=\"{evidence.get('code', '')}\"")
            lines.append("")

    if decisions:
        lines.extend(["## Governance decisions", ""])
        for decision in decisions:
            lines.append(
                f"- `{decision['module']}.{decision['function']}` → "
                f"**{decision['direction']}** ({decision['reason']})"
            )
        lines.append("")

    if suggestions:
        lines.extend(["## Code fix suggestions (not auto-applied)", ""])
        for suggestion in suggestions:
            lines.append(f"### `{suggestion['module']}.{suggestion['function']}`")
            lines.append(f"```\n{suggestion['message']}\n```")
            lines.append("")

    lines.extend([
        "## Out of scope",
        "",
        "- Automatic **code** modification (suggestions only)",
        "- Auto-fix of semantic candidates (HITL required)",
        "",
        "## Next steps (TODO)",
        "",
        "- Run `gh pr create` with this title/body after human review",
        "- Apply `patch.diff` to README/docstring only",
        "- Require human approval before merge (HOTL)",
    ])
    return "\n".join(lines)


def build_pr_request(report_path: Path, patch_path: Path | None = None) -> PRRequest:
    """Build a PRRequest from drift_report.json."""
    report = load_drift_report(report_path)
    resolved_patch = patch_path or report_path.parent / "patch.diff"
    return PRRequest(
        title=generate_pr_title(report),
        body=generate_pr_body(report, resolved_patch),
        patch_path=resolved_patch,
    )


class StubPRAgent(PRAgent):
    """
    Dry-run PR Agent.

    Generates PR title/body from drift_report.json and prints a preview.
    Does NOT execute `gh` or call the GitHub API.
  """

    def generate_dry_run(
        self,
        report_path: Path,
        patch_path: Path | None = None,
        *,
        base_branch: str = "main",
        head_branch: str = "docs/drift-fix",
    ) -> DryRunPRContent:
        """Generate dry-run PR content from a drift report."""
        report_path = report_path.resolve()
        resolved_patch = (patch_path or report_path.parent / "patch.diff").resolve()
        request = build_pr_request(report_path, resolved_patch)
        return DryRunPRContent(
            title=request.title,
            body=request.body,
            base_branch=base_branch,
            head_branch=head_branch,
            patch_path=resolved_patch,
            report_path=report_path,
        )

    def create_pr(self, request: PRRequest) -> PRResult:
        """Return dry-run preview without creating an actual GitHub PR."""
        preview = "\n".join([
            "=" * 60,
            "DRY-RUN PR PREVIEW (no gh command executed)",
            "=" * 60,
            "",
            f"Base branch : {request.base_branch}",
            f"Head branch : {request.head_branch}",
            f"Patch       : {request.patch_path}",
            "",
            "-" * 60,
            "TITLE",
            "-" * 60,
            request.title,
            "",
            "-" * 60,
            "BODY",
            "-" * 60,
            request.body,
            "",
            "=" * 60,
            "Use --create-pr --hotl-approved for real gh pr create",
            "=" * 60,
        ])
        return PRResult(
            success=True,
            pr_url=None,
            message=preview,
            dry_run=True,
        )

    def run_dry_run(
        self,
        report_path: Path,
        patch_path: Path | None = None,
        output_path: Path | None = None,
    ) -> DryRunPRContent:
        """Generate and optionally save dry-run PR preview."""
        content = self.generate_dry_run(report_path, patch_path)
        text = content.format_output()
        if output_path:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(text, encoding="utf-8")
        return content


def get_pr_agent(*, create_pr: bool = False) -> PRAgent:
    """Return GhPRAgent for real PR creation, else StubPRAgent (dry-run)."""
    if create_pr and shutil.which("gh"):
        return GhPRAgent()
    return StubPRAgent()


class GhPRAgent(PRAgent):
    """
    Full PR Agent — creates branch, applies doc patch, commits, pushes, opens PR via gh.

    Requires: git repo, gh CLI authenticated, HOTL approval, hooks passed.
    """

    def generate_dry_run(
        self,
        report_path: Path,
        patch_path: Path | None = None,
        **kwargs,
    ) -> DryRunPRContent:
        return StubPRAgent().generate_dry_run(report_path, patch_path, **kwargs)

    def create_pr(self, request: PRRequest) -> PRResult:
        if not shutil.which("gh"):
            return PRResult(
                success=False,
                pr_url=None,
                message="gh CLI not found. Install GitHub CLI and authenticate.",
                dry_run=False,
            )

        project_root = request.patch_path.parent
        # Walk up to find git root
        git_root = _find_git_root(project_root)
        if git_root is None:
            return PRResult(
                success=False, pr_url=None,
                message="Not a git repository — cannot create PR.",
                dry_run=False,
            )

        branch = f"{request.head_branch}-{uuid4().hex[:8]}"
        patch_text = ""
        if request.patch_path.exists():
            patch_text = request.patch_path.read_text(encoding="utf-8")

        try:
            _git_run(git_root, "checkout", request.base_branch)
            _git_run(git_root, "checkout", "-b", branch)
            modified_files: list[str] = []
            if patch_text.strip():
                from docs_code_drift_detector.patch_applier import apply_doc_patch_in_place

                modified_files = apply_doc_patch_in_place(git_root, patch_text)
            if not modified_files:
                return PRResult(
                    success=False, pr_url=None,
                    message="No changes to commit after applying patch.",
                    dry_run=False,
                )
            for rel_path in modified_files:
                _git_run(git_root, "add", rel_path.replace("\\", "/"))
            _git_run(git_root, "commit", "-m", request.title)
            _git_run(git_root, "push", "-u", "origin", branch)

            cmd = [
                "gh", "pr", "create",
                "--title", request.title,
                "--body", request.body,
                "--base", request.base_branch,
                "--head", branch,
            ]
            if request.draft:
                cmd.append("--draft")
            result = run_text(
                cmd,
                cwd=str(git_root),
                capture_output=True,
                timeout=120,
            )
            if result.returncode != 0:
                return PRResult(
                    success=False, pr_url=None,
                    message=f"gh pr create failed: {result.stderr.strip()}",
                    dry_run=False,
                )
            pr_url = result.stdout.strip()
            return PRResult(
                success=True,
                pr_url=pr_url,
                message=f"PR created: {pr_url}",
                dry_run=False,
            )
        except subprocess.CalledProcessError as exc:
            return PRResult(
                success=False, pr_url=None,
                message=f"Git operation failed: {exc}",
                dry_run=False,
            )

    def run_dry_run(
        self,
        report_path: Path,
        patch_path: Path | None = None,
        output_path: Path | None = None,
    ) -> DryRunPRContent:
        stub = StubPRAgent()
        return stub.run_dry_run(report_path, patch_path, output_path)


def _find_git_root(start: Path) -> Path | None:
    path = start.resolve()
    for parent in [path, *path.parents]:
        if (parent / ".git").exists():
            return parent
    return None


def _git_run(repo: Path, *args: str, capture: bool = False) -> str:
    result = run_text(
        ["git", *args],
        cwd=str(repo),
        capture_output=True,
        check=True,
        timeout=60,
    )
    return result.stdout if capture else ""

