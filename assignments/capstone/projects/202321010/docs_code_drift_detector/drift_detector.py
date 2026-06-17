"""Compare doc specs and code specs to detect drift."""

from __future__ import annotations

import re

from docs_code_drift_detector.models import DriftItem, DriftType, FunctionSpec


def _normalize_type_name(type_str: str | None) -> str | None:
    if type_str is None:
        return None
    cleaned = type_str.strip().lower()
    cleaned = re.sub(r"\s+", "", cleaned)
    aliases = {
        "dictionary": "dict",
        "listofdict": "list[dict]",
        "list[dict]": "list[dict]",
        "list[dicts]": "list[dict]",
        "none": "none",
        "null": "none",
    }
    return aliases.get(cleaned, cleaned)


def _base_type(type_str: str | None) -> str | None:
    if type_str is None:
        return None
    normalized = _normalize_type_name(type_str)
    if normalized is None:
        return None
    match = re.match(r"([a-z]+)", normalized)
    return match.group(1) if match else normalized


def _effective_return_type(spec: FunctionSpec) -> str | None:
    if spec.return_annotation:
        return spec.return_annotation
    if spec.inferred_returns:
        if len(spec.inferred_returns) == 1:
            return spec.inferred_returns[0]
        return "|".join(sorted(spec.inferred_returns))
    return None


def _is_structure_mismatch(doc_ret: str, code_ret: str) -> bool:
    """Detect structural differences like dict vs list[dict]."""
    doc_norm = _normalize_type_name(doc_ret) or ""
    code_norm = _normalize_type_name(code_ret) or ""

    if doc_norm == code_norm:
        return False

    doc_base = _base_type(doc_ret)
    code_base = _base_type(code_ret)

    if doc_base == code_base:
        return doc_norm != code_norm

    structure_pairs = {
        ("dict", "list"),
        ("list", "dict"),
        ("dict", "list[dict]"),
        ("list[dict]", "dict"),
    }
    return (doc_base, code_base) in structure_pairs or (
        doc_norm,
        code_norm,
    ) in {("dict", "list[dict]"), ("list[dict]", "dict")}


def _compare_parameters(
    doc_spec: FunctionSpec,
    code_spec: FunctionSpec,
) -> list[DriftItem]:
    drifts: list[DriftItem] = []
    doc_params = doc_spec.parameters
    code_params = code_spec.parameters

    if len(doc_params) != len(code_params):
        drifts.append(
            DriftItem(
                function=code_spec.name,
                module=code_spec.module,
                drift_type=DriftType.PARAMETER_COUNT_MISMATCH,
                doc_value=str(len(doc_params)),
                code_value=str(len(code_params)),
                confidence=0.95,
                evidence={
                    "doc": ", ".join(p.name for p in doc_params) or "(none)",
                    "code": ", ".join(p.name for p in code_params) or "(none)",
                },
                source_file=code_spec.source_file,
            )
        )
        return drifts

    for doc_p, code_p in zip(doc_params, code_params, strict=True):
        if doc_p.name != code_p.name:
            drifts.append(
                DriftItem(
                    function=code_spec.name,
                    module=code_spec.module,
                    drift_type=DriftType.PARAMETER_NAME_MISMATCH,
                    doc_value=doc_p.name,
                    code_value=code_p.name,
                    confidence=0.9,
                    evidence={
                        "doc": f"parameter '{doc_p.name}'",
                        "code": f"parameter '{code_p.name}'",
                    },
                    source_file=code_spec.source_file,
                )
            )

        doc_ann = _normalize_type_name(doc_p.annotation)
        code_ann = _normalize_type_name(code_p.annotation)
        if doc_ann and code_ann and doc_ann != code_ann:
            drifts.append(
                DriftItem(
                    function=code_spec.name,
                    module=code_spec.module,
                    drift_type=DriftType.PARAMETER_TYPE_MISMATCH,
                    doc_value=doc_p.annotation,
                    code_value=code_p.annotation,
                    confidence=0.88,
                    evidence={
                        "doc": f"{doc_p.name}: {doc_p.annotation}",
                        "code": f"{code_p.name}: {code_p.annotation}",
                    },
                    source_file=code_spec.source_file,
                )
            )

        if doc_p.default is not None or code_p.default is not None:
            doc_def = (doc_p.default or "").strip()
            code_def = (code_p.default or "").strip()
            if doc_def != code_def:
                drifts.append(
                    DriftItem(
                        function=code_spec.name,
                        module=code_spec.module,
                        drift_type=DriftType.PARAMETER_DEFAULT_MISMATCH,
                        doc_value=doc_p.default,
                        code_value=code_p.default,
                        confidence=0.85,
                        evidence={
                            "doc": f"{doc_p.name}={doc_p.default}",
                            "code": f"{code_p.name}={code_p.default}",
                        },
                        source_file=code_spec.source_file,
                    )
                )

    return drifts


def _compare_returns(
    doc_spec: FunctionSpec,
    code_spec: FunctionSpec,
) -> list[DriftItem]:
    drifts: list[DriftItem] = []
    doc_ret = _effective_return_type(doc_spec)
    code_ret = _effective_return_type(code_spec)

    if doc_ret is None or code_ret is None:
        return drifts

    doc_norm = _normalize_type_name(doc_ret)
    code_norm = _normalize_type_name(code_ret)

    if doc_norm == code_norm:
        return drifts

    if _is_structure_mismatch(doc_ret, code_ret):
        drifts.append(
            DriftItem(
                function=code_spec.name,
                module=code_spec.module,
                drift_type=DriftType.RETURN_STRUCTURE_MISMATCH,
                doc_value=doc_ret,
                code_value=code_ret,
                confidence=0.91,
                evidence={
                    "doc": f"returns {doc_ret}",
                    "code": f"returns {code_ret}",
                },
                source_file=code_spec.source_file,
            )
        )
    else:
        drifts.append(
            DriftItem(
                function=code_spec.name,
                module=code_spec.module,
                drift_type=DriftType.RETURN_TYPE_MISMATCH,
                doc_value=doc_ret,
                code_value=code_ret,
                confidence=0.9,
                evidence={
                    "doc": f"returns {doc_ret}",
                    "code": f"returns {code_ret}",
                },
                source_file=code_spec.source_file,
            )
        )

    return drifts


def _has_explicit_param_defaults(spec: FunctionSpec) -> bool:
    return any(p.default is not None for p in spec.parameters)


def _parameter_doc_spec(
    doc: FunctionSpec,
    readme: FunctionSpec | None,
) -> FunctionSpec:
    """
    Prefer README signatures for parameter/default comparison when the
    module docstring omits defaults but README documents them.
    """
    if readme is None or readme is doc:
        return doc
    if _has_explicit_param_defaults(readme) and not _has_explicit_param_defaults(doc):
        return readme
    return doc


def detect_drift(
    doc_specs: list[FunctionSpec],
    code_specs: list[FunctionSpec],
) -> list[DriftItem]:
    """Detect drift between documentation and code specifications."""
    doc_by_key: dict[tuple[str, str], FunctionSpec] = {}
    for spec in doc_specs:
        doc_by_key[(spec.module, spec.name)] = spec
        if spec.module == "readme":
            doc_by_key[("readme", spec.name)] = spec

    drifts: list[DriftItem] = []
    for code in code_specs:
        doc = doc_by_key.get((code.module, code.name))
        if doc is None:
            doc = doc_by_key.get(("readme", code.name))
        if doc is None:
            continue

        readme = doc_by_key.get(("readme", code.name))
        param_doc = _parameter_doc_spec(doc, readme)

        drifts.extend(_compare_parameters(param_doc, code))
        drifts.extend(_compare_returns(doc, code))

    return drifts
