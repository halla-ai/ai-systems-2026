"""AST-based Python source code analyzer."""

from __future__ import annotations

import ast
from pathlib import Path

from docs_code_drift_detector.models import FunctionSpec, ParameterSpec


def _annotation_to_str(node: ast.expr | None) -> str | None:
    if node is None:
        return None
    return ast.unparse(node)


def _default_to_str(node: ast.expr | None) -> str | None:
    if node is None:
        return None
    return ast.unparse(node)


def _infer_return_type(node: ast.expr | None) -> str | None:
    """Infer simple return types from return statement values."""
    if node is None:
        return "None"

    if isinstance(node, ast.Constant):
        if node.value is None:
            return "None"
        if isinstance(node.value, bool):
            return "bool"
        if isinstance(node.value, int):
            return "int"
        if isinstance(node.value, str):
            return "str"
        if isinstance(node.value, float):
            return "float"
        return None

    if isinstance(node, ast.List):
        return "list"
    if isinstance(node, ast.Dict):
        return "dict"
    if isinstance(node, ast.Tuple):
        return "tuple"
    if isinstance(node, ast.Set):
        return "set"
    if isinstance(node, ast.Name):
        if node.id == "None":
            return "None"
        return None
    if isinstance(node, ast.Call):
        if isinstance(node.func, ast.Name):
            name = node.func.id
            if name in ("list", "dict", "str", "int", "bool", "float", "tuple", "set"):
                return name
        return None

    return None


class _FunctionVisitor(ast.NodeVisitor):
    def __init__(self, module: str, source_file: str) -> None:
        self.module = module
        self.source_file = source_file
        self.functions: list[FunctionSpec] = []

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        if node.name.startswith("_") and not node.name.startswith("__"):
            return

        parameters: list[ParameterSpec] = []
        args = node.args

        defaults_offset = len(args.args) - len(args.defaults)
        for i, arg in enumerate(args.args):
            if arg.arg == "self":
                continue
            default = None
            default_idx = i - defaults_offset
            if default_idx >= 0:
                default = _default_to_str(args.defaults[default_idx])
            parameters.append(
                ParameterSpec(
                    name=arg.arg,
                    annotation=_annotation_to_str(arg.annotation),
                    default=default,
                )
            )

        for arg in args.kwonlyargs:
            default = None
            if arg.arg in [d for d in args.kw_defaults if d is not None]:
                idx = args.kwonlyargs.index(arg)
                if idx < len(args.kw_defaults) and args.kw_defaults[idx] is not None:
                    default = _default_to_str(args.kw_defaults[idx])
            parameters.append(
                ParameterSpec(
                    name=arg.arg,
                    annotation=_annotation_to_str(arg.annotation),
                    default=default,
                )
            )

        inferred = _collect_return_types(node)
        docstring = ast.get_docstring(node)

        self.functions.append(
            FunctionSpec(
                name=node.name,
                module=self.module,
                parameters=parameters,
                return_annotation=_annotation_to_str(node.returns),
                inferred_returns=inferred,
                has_docstring=docstring is not None,
                docstring=docstring,
                source_file=self.source_file,
                line_number=node.lineno,
                source="code",
            )
        )
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self.visit_FunctionDef(node)  # type: ignore[arg-type]


def _collect_return_types(func_node: ast.FunctionDef) -> list[str]:
    """Collect inferred return types from all return statements."""
    types: list[str] = []
    for node in ast.walk(func_node):
        if isinstance(node, ast.Return):
            inferred = _infer_return_type(node.value)
            if inferred and inferred not in types:
                types.append(inferred)
    return types


def analyze_file(path: Path, project_root: Path | None = None) -> list[FunctionSpec]:
    """Analyze a single Python file and extract function specs."""
    root = project_root or path.parent
    try:
        rel = str(path.relative_to(root))
    except ValueError:
        rel = str(path)

    module = rel.replace("\\", "/").removesuffix(".py").replace("/", ".")
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    visitor = _FunctionVisitor(module=module, source_file=rel)
    visitor.visit(tree)
    return visitor.functions


def analyze_project(
    project_root: Path,
    *,
    exclude_dirs: set[str] | None = None,
) -> list[FunctionSpec]:
    """Analyze all Python files under project_root."""
    exclude = exclude_dirs or {
        ".git",
        ".venv",
        "venv",
        "__pycache__",
        ".pytest_cache",
        "node_modules",
        "docs_code_drift_detector",
        "tests",
        "test",
    }
    specs: list[FunctionSpec] = []
    for path in sorted(project_root.rglob("*.py")):
        try:
            rel_parts = path.relative_to(project_root).parts
        except ValueError:
            continue
        if rel_parts[0] in exclude:
            continue
        if any(part in exclude for part in rel_parts[1:]):
            continue
        specs.extend(analyze_file(path, project_root))
    return specs
