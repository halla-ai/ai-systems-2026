"""Tests for patch applier."""

from pathlib import Path

from docs_code_drift_detector.patch_applier import (
    apply_doc_patch_in_place,
    apply_doc_patch_to_temp,
    files_from_patch,
)

PATCH = """--- a/api.py
+++ b/api.py
@@ -4,4 +4,4 @@
 Returns:
-    dict: Parsed data.
+    list
"""


def test_apply_doc_patch_to_temp(sample_project=None):
    fixture = Path(__file__).parent / "fixtures" / "sample_project"
    result = apply_doc_patch_to_temp(fixture, PATCH)
    assert result.success is True
    assert result.temp_dir is not None
    if result.temp_dir:
        import shutil
        shutil.rmtree(result.temp_dir.parent, ignore_errors=True)


def test_apply_doc_patch_in_place(tmp_path):
    api = tmp_path / "api.py"
    api.write_text(
        'def f():\n    """X."""\n    return []\n',
        encoding="utf-8",
    )
    patch = """--- a/api.py
+++ b/api.py
@@ -1,3 +1,3 @@
 def f():
-    \"\"\"X.\"\"\"
+    \"\"\"Y.\"\"\"
     return []
"""
    modified = apply_doc_patch_in_place(tmp_path, patch)
    assert "api.py" in modified
    assert '"""Y."""' in api.read_text(encoding="utf-8")


def test_files_from_patch_lists_paths():
    paths = files_from_patch(PATCH)
    assert paths == ["api.py"]
