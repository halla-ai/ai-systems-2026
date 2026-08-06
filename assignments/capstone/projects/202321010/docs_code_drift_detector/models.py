"""Shared data models for docs-code drift detection."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any


class DriftType(str, Enum):
    RETURN_TYPE_MISMATCH = "return_type_mismatch"
    PARAMETER_COUNT_MISMATCH = "parameter_count_mismatch"
    PARAMETER_NAME_MISMATCH = "parameter_name_mismatch"
    PARAMETER_TYPE_MISMATCH = "parameter_type_mismatch"
    PARAMETER_DEFAULT_MISMATCH = "parameter_default_mismatch"
    RETURN_STRUCTURE_MISMATCH = "return_structure_mismatch"
    SEMANTIC_MISMATCH = "semantic_mismatch"


class FixDirection(str, Enum):
    UPDATE_DOC = "update_doc"
    SUGGEST_CODE = "suggest_code"
    HUMAN_REVIEW = "human_review"


@dataclass
class ParameterSpec:
    name: str
    annotation: str | None = None
    default: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class FunctionSpec:
    name: str
    module: str
    parameters: list[ParameterSpec] = field(default_factory=list)
    return_annotation: str | None = None
    inferred_returns: list[str] = field(default_factory=list)
    has_docstring: bool = False
    docstring: str | None = None
    source_file: str = ""
    line_number: int = 0
    source: str = "code"  # "code" | "doc"

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "module": self.module,
            "parameters": [p.to_dict() for p in self.parameters],
            "return_annotation": self.return_annotation,
            "inferred_returns": self.inferred_returns,
            "has_docstring": self.has_docstring,
            "source_file": self.source_file,
            "line_number": self.line_number,
            "source": self.source,
        }


@dataclass
class DriftItem:
    function: str
    module: str
    drift_type: DriftType
    doc_value: str | None
    code_value: str | None
    confidence: float
    evidence: dict[str, str]
    source_file: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "function": self.function,
            "module": self.module,
            "drift_type": self.drift_type.value,
            "doc_value": self.doc_value,
            "code_value": self.code_value,
            "confidence": self.confidence,
            "evidence": self.evidence,
            "source_file": self.source_file,
        }


@dataclass
class GovernanceDecision:
    function: str
    module: str
    direction: FixDirection
    reason: str
    has_tests: bool
    has_typing: bool
    has_docstring_contract: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "function": self.function,
            "module": self.module,
            "direction": self.direction.value,
            "reason": self.reason,
            "has_tests": self.has_tests,
            "has_typing": self.has_typing,
            "has_docstring_contract": self.has_docstring_contract,
        }


@dataclass
class CodeFixSuggestion:
    function: str
    module: str
    message: str
    line_hint: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class DriftReport:
    project_root: str
    functions_scanned: int
    drifts: list[DriftItem] = field(default_factory=list)
    decisions: list[GovernanceDecision] = field(default_factory=list)
    code_suggestions: list[CodeFixSuggestion] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "project_root": self.project_root,
            "functions_scanned": self.functions_scanned,
            "drift_count": len(self.drifts),
            "drifts": [d.to_dict() for d in self.drifts],
            "decisions": [d.to_dict() for d in self.decisions],
            "code_suggestions": [s.to_dict() for s in self.code_suggestions],
        }
