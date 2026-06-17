"""Tests for PR agent staging only patched files."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from docs_code_drift_detector.pr_agent import GhPRAgent, PRRequest

PATCH = """--- a/README.md
+++ b/README.md
@@ -1,2 +1,2 @@
 # App
-`foo() -> int`
+`foo() -> str`
"""


def test_create_pr_git_add_excludes_output_dir(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "README.md").write_text("# App\n`foo() -> int`\n", encoding="utf-8")
    (repo / "output").mkdir()
    (repo / "output" / "junk.json").write_text("{}", encoding="utf-8")

    patch_path = tmp_path / "patch.diff"
    patch_path.write_text(PATCH, encoding="utf-8")

    git_add_args: list[str] = []

    def fake_git_run(r, *args, capture=False, **kwargs):
        if args and args[0] == "add":
            git_add_args.extend(args[1:])
        return ""

    agent = GhPRAgent()
    request = PRRequest(title="docs: test", body="body", patch_path=patch_path)

    with patch("docs_code_drift_detector.pr_agent._find_git_root", return_value=repo):
        with patch("docs_code_drift_detector.pr_agent._git_run", side_effect=fake_git_run):
            with patch("docs_code_drift_detector.pr_agent.shutil.which", return_value="/gh"):
                with patch("docs_code_drift_detector.pr_agent.run_text") as mock_gh:
                    mock_gh.return_value = MagicMock(returncode=0, stdout="https://github.com/x/y/pull/1")
                    result = agent.create_pr(request)

    assert result.success is True
    assert git_add_args == ["README.md"]
    assert not any("output" in p for p in git_add_args)
