from docs_code_drift_detector.provider.llm_provider import select_provider
from docs_code_drift_detector.provider.static_provider import (
    STATIC_AST_PROFILE,
    get_active_provider,
    select_fallback,
)

__all__ = [
    "STATIC_AST_PROFILE",
    "get_active_provider",
    "select_fallback",
    "select_provider",
]
