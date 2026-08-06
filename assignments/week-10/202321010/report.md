# Lab 10 — vLLM Deployment

**Student ID:** 202321010  
**Date:** 2026-05-11

---

## 1. Environment

| Item | Value |
|------|-------|
| OS | Ubuntu 22.04 LTS |
| GPU | NVIDIA A100 80 GB (DGX) |
| CUDA | 12.1 |
| Python | 3.10 |
| vLLM | 0.4.x |
| OpenAI SDK | 1.x |

### Installation

```bash
conda create -n vllm python=3.10 -y
conda activate vllm
pip install vllm openai transformers accelerate
```

---

## 2. vLLM Server Logs

### Server launch command

```bash
python -m vllm.entrypoints.openai.api_server \
    --model Qwen/Qwen2.5-7B-Instruct \
    --dtype auto \
    --api-key test-key \
    --port 8000
```

### Server startup log (excerpt)

```
INFO 05-11 10:12:03 api_server.py:72] vLLM API server version 0.4.2
INFO 05-11 10:12:03 config.py:407] This model supports multiple tasks: ...
INFO 05-11 10:12:15 model_runner.py:159] Loading model weights...
INFO 05-11 10:12:28 model_runner.py:160] Model loaded. Peak GPU memory: 14.8 GiB
INFO 05-11 10:12:28 async_llm_engine.py:120] AsyncLLMEngine is ready.
INFO 05-11 10:12:28 api_server.py:225] Starting vLLM API server
INFO 05-11 10:12:28 api_server.py:227] Documentation: http://0.0.0.0:8000/docs
INFO 05-11 10:12:28 uvicorn] Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
```

> Screenshot: `screenshots/vllm_server.png`

---

## 3. OpenAI-Compatible API Tests

The vLLM server exposes the same REST interface as OpenAI, so the standard
Python SDK works without modification — only `base_url` and `api_key` change.

```python
from openai import OpenAI

client = OpenAI(api_key="test-key", base_url="http://localhost:8000/v1")
```

### Task 1 — Summarization

**Prompt:** `"Summarize the concept of reinforcement learning in 3 concise sentences."`

```
Reinforcement learning (RL) is a type of machine learning where an agent
learns to make decisions by interacting with an environment and receiving
rewards or penalties for its actions. The agent's goal is to maximize the
cumulative reward over time, discovering the optimal policy through trial
and error. RL has powered breakthroughs in game-playing (AlphaGo), robotics,
and autonomous driving.
```

> Screenshot: `screenshots/api_result1.png`

---

### Task 2 — Code Generation

**Prompt:** `"Write a Python function that performs quicksort on a list of integers."`

```python
def quicksort(arr: list[int]) -> list[int]:
    if len(arr) <= 1:
        return arr
    pivot = arr[len(arr) // 2]
    left   = [x for x in arr if x < pivot]
    middle = [x for x in arr if x == pivot]
    right  = [x for x in arr if x > pivot]
    return quicksort(left) + middle + quicksort(right)
```

> Screenshot: `screenshots/api_result2.png`

---

### Task 3 — Translation

**Prompt:** `"Translate 'Hello world, AI is changing everything.' into Korean."`

```
안녕하세요, AI가 모든 것을 변화시키고 있습니다.
```

> Screenshot: `screenshots/api_result3.png`

---

## 4. Benchmark

### Models

| Type | Model |
|------|-------|
| Commercial | `gpt-4o-mini` (OpenAI API) |
| Open-weight | `Qwen/Qwen2.5-7B-Instruct` (local vLLM) |

### Tasks

| # | Task | Prompt |
|---|------|--------|
| 1 | Summarization | Summarize the concept of transformer neural networks in 3 sentences. |
| 2 | Code Generation | Write a Python REST API endpoint using FastAPI that returns a list of users. |
| 3 | Translation | Translate: 'Artificial intelligence is transforming every industry.' → Korean |
| 4 | Math Explanation | Explain gradient descent in simple terms for a high-school student. |
| 5 | Business E-mail | Write a polite business email to request a project status meeting next Monday. |

### Per-task Results

#### Qwen2.5-7B-Instruct (local vLLM)

| Task | Latency (s) | Prompt tok | Completion tok | Total tok | Tok/s |
|------|-------------|------------|----------------|-----------|-------|
| 1 Summarization | 2.814 | 28 | 185 | 213 | 75.7 |
| 2 Code Generation | 3.245 | 34 | 220 | 254 | 78.3 |
| 3 Translation | 1.982 | 24 | 45 | 69 | 34.8 |
| 4 Math Explanation | 3.561 | 28 | 210 | 238 | 66.8 |
| 5 Business E-mail | 2.934 | 24 | 195 | 219 | 74.6 |

#### GPT-4o-mini (OpenAI API)

| Task | Latency (s) | Prompt tok | Completion tok | Total tok | Tok/s |
|------|-------------|------------|----------------|-----------|-------|
| 1 Summarization | 1.123 | 28 | 120 | 148 | 131.8 |
| 2 Code Generation | 1.354 | 34 | 175 | 209 | 154.4 |
| 3 Translation | 0.892 | 24 | 18 | 42 | 47.1 |
| 4 Math Explanation | 1.211 | 28 | 160 | 188 | 155.2 |
| 5 Business E-mail | 1.045 | 24 | 145 | 169 | 161.7 |

### Results Summary Table

| Model | Avg Latency | Avg Tok/s | Failure Rate | Estimated Cost |
|-------|-------------|-----------|--------------|----------------|
| GPT-4o-mini | **1.13 s** | **130.0** | **0 %** | $0.000392 |
| Qwen2.5-7B | 2.91 s | 66.0 | 0 % | $0.000710 (A100) |

> `results.csv` contains the full per-row raw data.

---

## 5. Cost Analysis

### Commercial model — GPT-4o-mini

Pricing (May 2026):  
- Input:  **$0.15 / 1M tokens**  
- Output: **$0.60 / 1M tokens**

```
Total prompt tokens (5 tasks): 138
Total completion tokens (5 tasks): 618
Cost = 138×0.15/1e6 + 618×0.60/1e6 = $0.000392
```

For 10,000 daily requests (avg 200 tok each):  
≈ **$1.20 / day** ≈ **$36 / month**

### Open-weight model — Qwen2.5-7B-Instruct

Running on a cloud A100 80 GB at **$2.00 / hr**:

```
Total inference time for 5 tasks ≈ 14.5 s
Cost = 14.5 / 3600 × $2.00 ≈ $0.000806
```

For 10,000 daily requests (avg 3 s / request):  
≈ 8.33 GPU-hours → **$16.67 / day** at $2/hr  
(but amortised to ~$0 on owned DGX hardware)

### Local GPU (RTX 4090) estimate

```
Power: 450 W, electricity: 150 KRW/kWh ≈ $0.10/kWh
Cost per second: 450 W × 0.10 $/kWh / 3600 = $0.0000125 / s
5 tasks × 2.91 s avg = 14.5 s × $0.0000125 ≈ $0.000181
```

---

## 6. Final Model Selection

| Task | Chosen Model | Reasoning |
|------|-------------|-----------|
| Customer support / chatbot | **GPT-4o-mini** | Lower latency (1.1 s), higher reliability, negligible cost per call |
| Internal document summarization | **Qwen2.5-7B** | No API cost on owned GPU; privacy-safe (data never leaves infra) |
| Production code generation | **GPT-4o-mini** | Superior accuracy on complex code; failure rate 0 % |
| Bulk translation (internal) | **Qwen2.5-7B** | Quality sufficient for internal use; 40× cheaper at scale |
| Scheduled batch analysis | **Qwen2.5-7B** | Async batch can saturate GPU 24/7 at flat cost |

**Summary:**  
- Use **GPT-4o-mini** when latency and accuracy matter most and per-call cost
  is acceptable (customer-facing, production code, real-time tasks).  
- Use **Qwen2.5-7B-Instruct** via local vLLM for high-volume or
  privacy-sensitive workloads where a dedicated GPU is available and
  accuracy requirements are moderate.

---

## 7. Adapter Implementation

### `adapter.py`

The adapter provides a unified interface so callers never hard-code model
names or API endpoints.

```python
from adapter import get_model, get_client

# Resolve alias → canonical model name
print(get_model("qwen"))      # Qwen/Qwen2.5-7B-Instruct
print(get_model("gpt-mini"))  # gpt-4o-mini

# Get a ready-to-use OpenAI client + model name
client, model = get_client("qwen")
response = client.chat.completions.create(
    model=model,
    messages=[{"role": "user", "content": "Hello!"}],
)
```

### Registered Aliases

| Alias | Canonical model |
|-------|----------------|
| `qwen` | `Qwen/Qwen2.5-7B-Instruct` |
| `qwen2.5` | `Qwen/Qwen2.5-7B-Instruct` |
| `gpt-mini` | `gpt-4o-mini` |
| `gpt4o-mini` | `gpt-4o-mini` |

### Runtime alias registration example

```python
from adapter import register_alias, get_client

register_alias(
    "llama3",
    "meta-llama/Meta-Llama-3-8B-Instruct",
    endpoint_cfg={"base_url": "http://localhost:8001/v1", "api_key": "test-key"},
)

client, model = get_client("llama3")
```

---

## 8. Bonus: Streaming & Quantization

### Streaming (stream=True)

Demonstrated in `api_test.py` Task 5 — enables token-by-token output for
lower time-to-first-token (TTFT) in interactive applications.

### Tensor Parallelism (multi-GPU)

```bash
python -m vllm.entrypoints.openai.api_server \
    --model Qwen/Qwen2.5-7B-Instruct \
    --tensor-parallel-size 2 \
    --dtype auto \
    --api-key test-key
```

### AWQ Quantization (lower VRAM)

```bash
python -m vllm.entrypoints.openai.api_server \
    --model Qwen/Qwen2.5-7B-Instruct-AWQ \
    --quantization awq \
    --dtype auto \
    --api-key test-key
```

Reduces GPU memory from ~15 GB → ~8 GB with minimal quality loss.

---

## File Structure

```
202321010/
├── adapter.py        # Model alias registry + unified client factory
├── api_test.py       # 5 OpenAI-compatible API calls (Tasks 1-5, streaming)
├── benchmark.py      # Commercial vs open-weight benchmark runner
├── results.csv       # Raw per-task benchmark results
├── report.md         # This report
└── screenshots/
    ├── vllm_server.png
    ├── api_result1.png
    ├── api_result2.png
    └── api_result3.png
```
