"""Minimal tests for benchmark fixture."""
import importlib.util
from pathlib import Path

def test_module_imports():
    api_path = Path(__file__).resolve().parent.parent / "api.py"
    spec = importlib.util.spec_from_file_location("benchmark_api", api_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert hasattr(mod, "clean_01")
