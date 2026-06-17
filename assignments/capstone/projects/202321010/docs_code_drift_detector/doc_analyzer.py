"""README and docstring analyzer (regex-based MVP)."""

from __future__ import annotations

import re
from pathlib import Path

from docs_code_drift_detector.models import FunctionSpec, ParameterSpec

# func(name: type, name2: type = default) -> return_type
_SIGNATURE_RE = re.compile(
    r"(?P<name>[a-zA-Z_][a-zA-Z0-9_]*)\s*"
    r"\(\s*(?P<params>[^)]*)\s*\)"
    r"(?:\s*->\s*(?P<return>[^\n`:]+))?",
    re.MULTILINE,
)

# `func(...)` inline code blocks
_INLINE_SIG_RE = re.compile(
    r"`(?P<name>[a-zA-Z_][a-zA-Z0-9_]*)\s*"
    r"\(\s*(?P<params>[^)]*)\s*\)"
    r"(?:\s*->\s*(?P<return>[^`]+))?`"
)

# Returns: dict / list[str] etc.
_RETURNS_LINE_RE = re.compile(
    r"^\s*(?:Returns?|Return)\s*:\s*(?P<return>.+)$",
    re.MULTILINE | re.IGNORECASE,
)

# Args section: name (type): description  OR  name: type
_ARG_LINE_RE = re.compile(
    r"^\s*(?P<name>[a-zA-Z_][a-zA-Z0-9_]*)\s*"
    r"(?:\((?P<type_paren>[^)]+)\)|:\s*(?P<type_colon>[^\s,:]+))"
    r"(?:\s*[,:]\s*.+)?$",
    re.MULTILINE,
)


def _parse_params(params_str: str) -> list[ParameterSpec]:
    if not params_str.strip():
        return []

    params: list[ParameterSpec] = []
    for part in _split_params(params_str):
        part = part.strip()
        if not part:
            continue
        match = re.match(
            r"(?P<name>[a-zA-Z_][a-zA-Z0-9_]*)\s*"
            r"(?::\s*(?P<annotation>[^=]+))?"
            r"(?:\s*=\s*(?P<default>.+))?",
            part,
        )
        if match:
            params.append(
                ParameterSpec(
                    name=match.group("name"),
                    annotation=match.group("annotation").strip()
                    if match.group("annotation")
                    else None,
                    default=match.group("default").strip()
                    if match.group("default")
                    else None,
                )
            )
    return params


def _split_params(params_str: str) -> list[str]:
    """Split parameter string respecting nested brackets."""
    parts: list[str] = []
    current: list[str] = []
    depth = 0
    for ch in params_str:
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
        if ch == "," and depth == 0:
            parts.append("".join(current))
            current = []
        else:
            current.append(ch)
    if current:
        parts.append("".join(current))
    return parts


def _normalize_type(type_str: str | None) -> str | None:
    if type_str is None:
        return None
    cleaned = type_str.strip().rstrip(".")
    aliases = {
        "dictionary": "dict",
        "list of dict": "list[dict]",
        "list of dictionaries": "list[dict]",
        "none": "None",
    }
    lower = cleaned.lower()
    return aliases.get(lower, cleaned)


def _spec_from_match(
    name: str,
    params_str: str,
    return_str: str | None,
    *,
    module: str = "readme",
    source_file: str = "README.md",
) -> FunctionSpec:
    return FunctionSpec(
        name=name,
        module=module,
        parameters=_parse_params(params_str),
        return_annotation=_normalize_type(return_str),
        source_file=source_file,
        source="doc",
    )


def parse_readme(readme_path: Path) -> list[FunctionSpec]:
    """Extract function signatures from README.md."""
    if not readme_path.exists():
        return []

    content = readme_path.read_text(encoding="utf-8")
    specs: dict[str, FunctionSpec] = {}

    for pattern in (_INLINE_SIG_RE, _SIGNATURE_RE):
        for match in pattern.finditer(content):
            name = match.group("name")
            if name in ("if", "for", "while", "def", "class", "return"):
                continue
            spec = _spec_from_match(
                name,
                match.group("params") or "",
                match.group("return"),
                source_file=str(readme_path.name),
            )
            specs[name] = spec

    return list(specs.values())


def parse_docstring(func_name: str, docstring: str, module: str, source_file: str) -> FunctionSpec | None:
    """Extract function contract from a docstring."""
    if not docstring:
        return None

    params: list[ParameterSpec] = []
    return_type: str | None = None

    args_match = re.search(
        r"(?:Args|Arguments|Parameters)\s*:\s*\n(?P<body>(?:[ \t]+.+\n?)+)",
        docstring,
        re.IGNORECASE,
    )
    if args_match:
        for line in args_match.group("body").splitlines():
            m = _ARG_LINE_RE.match(line)
            if m:
                ann = m.group("type_paren") or m.group("type_colon")
                params.append(
                    ParameterSpec(
                        name=m.group("name"),
                        annotation=_normalize_type(ann),
                    )
                )

    ret_match = _RETURNS_LINE_RE.search(docstring)
    if ret_match:
        return_type = _normalize_type(ret_match.group("return"))

    sig_match = _SIGNATURE_RE.search(docstring.replace("\n", " "))
    if sig_match and sig_match.group("name") == func_name:
        if not params:
            params = _parse_params(sig_match.group("params") or "")
        if not return_type:
            return_type = _normalize_type(sig_match.group("return"))

    if not params and not return_type:
        return None

    return FunctionSpec(
        name=func_name,
        module=module,
        parameters=params,
        return_annotation=return_type,
        has_docstring=True,
        docstring=docstring,
        source_file=source_file,
        source="doc",
    )


def analyze_docs(
    project_root: Path,
    code_specs: list[FunctionSpec] | None = None,
    *,
    include_api_docs: bool = True,
) -> list[FunctionSpec]:
    """Analyze README, docstrings, and API docs (OpenAPI/Sphinx)."""
    specs: dict[tuple[str, str], FunctionSpec] = {}
    by_name: dict[str, FunctionSpec] = {}

    readme = project_root / "README.md"
    for spec in parse_readme(readme):
        specs[(spec.module, spec.name)] = spec
        by_name[spec.name] = spec

    if include_api_docs:
        from docs_code_drift_detector.api_doc_parser import discover_api_docs
        for spec in discover_api_docs(project_root):
            specs[(spec.module, spec.name)] = spec
            if spec.name not in by_name:
                by_name[spec.name] = spec

    if code_specs:
        for code in code_specs:
            if code.docstring:
                doc_spec = parse_docstring(
                    code.name,
                    code.docstring,
                    code.module,
                    code.source_file,
                )
                if doc_spec:
                    key = (code.module, code.name)
                    if key not in specs:
                        specs[key] = doc_spec

    return list(specs.values())
