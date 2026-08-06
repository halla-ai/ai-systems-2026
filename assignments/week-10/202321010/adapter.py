"""
adapter.py - Model Adapter for Lab 10: vLLM Deployment

Provides alias registration and unified interface for
both commercial (GPT-4o-mini) and open-weight (Qwen2.5-7B-Instruct) models.
"""

from __future__ import annotations

import os
from typing import Optional
from openai import OpenAI

# ---------------------------------------------------------------------------
# Alias registry
# ---------------------------------------------------------------------------

MODEL_ALIASES: dict[str, str] = {
    # Open-weight (served via local vLLM)
    "qwen":        "Qwen/Qwen2.5-7B-Instruct",
    "qwen2.5":     "Qwen/Qwen2.5-7B-Instruct",
    # Commercial (OpenAI)
    "gpt-mini":    "gpt-4o-mini",
    "gpt4o-mini":  "gpt-4o-mini",
}

# Endpoint registry — maps each alias to its base_url and api_key env-var
ENDPOINT_CONFIG: dict[str, dict] = {
    "Qwen/Qwen2.5-7B-Instruct": {
        "base_url": os.environ.get("VLLM_BASE_URL", "http://localhost:8000/v1"),
        "api_key":  os.environ.get("VLLM_API_KEY",  "test-key"),
    },
    "gpt-4o-mini": {
        "base_url": "https://api.openai.com/v1",
        "api_key":  os.environ.get("OPENAI_API_KEY", ""),
    },
}

# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------

def get_model(alias: str) -> str:
    """Resolve an alias to the canonical model identifier.

    Parameters
    ----------
    alias : str
        Short name registered in MODEL_ALIASES.

    Returns
    -------
    str
        Canonical model identifier (e.g. 'Qwen/Qwen2.5-7B-Instruct').

    Raises
    ------
    ValueError
        When the alias is not registered.
    """
    key = alias.lower().strip()
    if key not in MODEL_ALIASES:
        raise ValueError(
            f"Unknown alias: '{alias}'. "
            f"Available aliases: {list(MODEL_ALIASES.keys())}"
        )
    return MODEL_ALIASES[key]


def get_client(alias: str) -> tuple[OpenAI, str]:
    """Return a configured OpenAI client and canonical model name for *alias*.

    Parameters
    ----------
    alias : str
        Registered model alias.

    Returns
    -------
    tuple[OpenAI, str]
        ``(client, model_name)`` ready to pass to
        ``client.chat.completions.create(model=model_name, ...)``.
    """
    model_name = get_model(alias)
    cfg = ENDPOINT_CONFIG.get(model_name, {})

    client = OpenAI(
        api_key=cfg.get("api_key", ""),
        base_url=cfg.get("base_url", "https://api.openai.com/v1"),
    )
    return client, model_name


def list_aliases() -> dict[str, str]:
    """Return a copy of the full alias → model mapping."""
    return dict(MODEL_ALIASES)


def register_alias(alias: str, model_name: str, endpoint_cfg: Optional[dict] = None) -> None:
    """Dynamically register a new alias at runtime.

    Parameters
    ----------
    alias : str
        Short name to register (case-insensitive).
    model_name : str
        Canonical model identifier.
    endpoint_cfg : dict, optional
        ``{"base_url": ..., "api_key": ...}`` for the model endpoint.
        If omitted, falls back to the vLLM local endpoint defaults.
    """
    MODEL_ALIASES[alias.lower().strip()] = model_name
    if endpoint_cfg:
        ENDPOINT_CONFIG[model_name] = endpoint_cfg


# ---------------------------------------------------------------------------
# Quick demo
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("=== Registered aliases ===")
    for alias, model in list_aliases().items():
        print(f"  {alias!r:15s} -> {model}")

    print()
    for alias in ("qwen", "gpt-mini"):
        resolved = get_model(alias)
        print(f"get_model('{alias}') => '{resolved}'")
