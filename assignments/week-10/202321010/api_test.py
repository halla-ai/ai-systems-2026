"""
api_test.py - OpenAI-Compatible API Call Tests (Lab 10)

Demonstrates at least 3 vLLM API calls using the OpenAI Python SDK.
Assumes a running vLLM server at http://localhost:8000
with:
    python -m vllm.entrypoints.openai.api_server \
        --model Qwen/Qwen2.5-7B-Instruct \
        --dtype auto \
        --api-key test-key \
        --port 8000
"""

import json
import time
from openai import OpenAI

# ---------------------------------------------------------------------------
# Client configuration
# ---------------------------------------------------------------------------

VLLM_BASE_URL = "http://localhost:8000/v1"
VLLM_API_KEY  = "test-key"
MODEL         = "Qwen/Qwen2.5-7B-Instruct"

client = OpenAI(api_key=VLLM_API_KEY, base_url=VLLM_BASE_URL)

# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def call(task_name: str, prompt: str, **kwargs) -> None:
    """Send a single chat-completion request and pretty-print the result."""
    print(f"\n{'='*60}")
    print(f"[Task] {task_name}")
    print(f"[Prompt] {prompt}")
    print("-" * 60)

    start = time.perf_counter()
    response = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=300,
        temperature=0.7,
        **kwargs,
    )
    elapsed = time.perf_counter() - start

    content = response.choices[0].message.content
    usage   = response.usage

    print(f"[Response]\n{content}")
    print(f"\n[Usage]  prompt={usage.prompt_tokens}  completion={usage.completion_tokens}  total={usage.total_tokens}")
    print(f"[Latency] {elapsed:.3f}s  ({usage.total_tokens / elapsed:.1f} tok/s)")

# ---------------------------------------------------------------------------
# Test cases (minimum 3 as required by the assignment)
# ---------------------------------------------------------------------------

def main() -> None:
    print("=" * 60)
    print("  Lab 10 — OpenAI-Compatible API Test (vLLM)")
    print(f"  Endpoint : {VLLM_BASE_URL}")
    print(f"  Model    : {MODEL}")
    print("=" * 60)

    # --- Task 1: Summarization ---
    call(
        task_name="Summarization",
        prompt="Summarize the concept of reinforcement learning in 3 concise sentences.",
    )

    # --- Task 2: Code generation ---
    call(
        task_name="Code Generation",
        prompt="Write a Python function that performs quicksort on a list of integers.",
    )

    # --- Task 3: Translation ---
    call(
        task_name="Translation",
        prompt="Translate the following sentence into Korean: 'Hello world, AI is changing everything.'",
    )

    # --- Task 4: Math explanation (bonus) ---
    call(
        task_name="Math Explanation",
        prompt="Explain gradient descent in simple terms for a beginner.",
    )

    # --- Task 5: Streaming demo (bonus) ---
    print(f"\n{'='*60}")
    print("[Task] Streaming — Business E-mail (stream=True)")
    print("-" * 60)

    start = time.perf_counter()
    stream = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": "Write a short polite business email requesting a meeting next week."}],
        max_tokens=250,
        temperature=0.7,
        stream=True,
    )

    collected = []
    for chunk in stream:
        delta = chunk.choices[0].delta.content or ""
        print(delta, end="", flush=True)
        collected.append(delta)

    elapsed = time.perf_counter() - start
    total_chars = sum(len(c) for c in collected)
    print(f"\n[Approx chars] {total_chars}  [Latency] {elapsed:.3f}s")

    print(f"\n{'='*60}")
    print("All API tests completed successfully.")
    print("=" * 60)


if __name__ == "__main__":
    main()
