"""Execution-based return type verification (§2.4 dynamic validation)."""

from __future__ import annotations

import json
import subprocess
import sys
import textwrap
from pathlib import Path

from docs_code_drift_detector.models import FunctionSpec
from docs_code_drift_detector.subprocess_compat import run_text

_VERIFY_SCRIPT = textwrap.dedent('''
import importlib.util
import json
import sys
from pathlib import Path

project_root = Path(sys.argv[1])
module_path = sys.argv[2]
func_name = sys.argv[3]

spec = importlib.util.spec_from_file_location("target_mod", module_path)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
fn = getattr(mod, func_name, None)
if fn is None:
    print(json.dumps({"error": "function not found"}))
    sys.exit(0)

# Build minimal call args from defaults
import inspect
sig = inspect.signature(fn)
args = []
kwargs = {}
for name, param in sig.parameters.items():
    if name in ("self", "cls"):
        continue
    if param.default is not inspect.Parameter.empty:
        kwargs[name] = param.default
    elif param.annotation in (int, "int"):
        kwargs[name] = 0
    elif param.annotation in (str, "str"):
        kwargs[name] = ""
    elif param.annotation in (bool, "bool"):
        kwargs[name] = False
    elif param.kind == inspect.Parameter.VAR_POSITIONAL:
        continue
    elif param.kind == inspect.Parameter.VAR_KEYWORD:
        continue
    else:
        kwargs[name] = None

try:
    result = fn(*args, **kwargs)
    rtype = type(result).__name__
    if rtype == "NoneType":
        rtype = "None"
    print(json.dumps({"runtime_type": rtype, "ok": True}))
except Exception as e:
    print(json.dumps({"error": str(e), "ok": False}))
''')


def _type_name_of_value(type_str: str) -> str:
    mapping = {"NoneType": "None", "dict": "dict", "list": "list", "str": "str", "int": "int", "bool": "bool"}
    return mapping.get(type_str, type_str)


def verify_function_runtime(
    project_root: Path,
    func_spec: FunctionSpec,
    *,
    timeout_sec: int = 5,
) -> str | None:
    """
    Run function in isolated subprocess and return observed runtime type.
    Returns None if verification cannot run safely.
    """
    if func_spec.name.startswith("_"):
        return None
    source = project_root / func_spec.source_file
    if not source.exists():
        return None

    try:
        result = run_text(
            [sys.executable, "-c", _VERIFY_SCRIPT, str(project_root), str(source), func_spec.name],
            capture_output=True,
            timeout=timeout_sec,
            cwd=str(project_root),
        )
        if result.returncode != 0:
            return None
        data = json.loads(result.stdout.strip() or "{}")
        if data.get("ok") and data.get("runtime_type"):
            return _type_name_of_value(data["runtime_type"])
    except (subprocess.TimeoutExpired, json.JSONDecodeError, OSError):
        return None
    return None


def enrich_specs_with_runtime(
    project_root: Path,
    specs: list[FunctionSpec],
) -> tuple[list[FunctionSpec], list[dict]]:
    """Add runtime-verified return types to code specs."""
    log: list[dict] = []
    for spec in specs:
        runtime_type = verify_function_runtime(project_root, spec)
        if runtime_type:
            if runtime_type not in spec.inferred_returns:
                spec.inferred_returns.append(runtime_type)
            log.append({
                "function": spec.name,
                "module": spec.module,
                "runtime_type": runtime_type,
                "verified": True,
            })
        else:
            log.append({
                "function": spec.name,
                "module": spec.module,
                "verified": False,
            })
    return specs, log
