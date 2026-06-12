# MemoryFlow AI

MemoryFlow AI is a closed-loop memory agent demo for reducing context loss in long conversations. The current project includes a Streamlit web UI and Gemini-backed final response generation while keeping the MemoryFlow memory pipeline separate from the LLM.

Gemini is used only to write the final natural-language response. The core MemoryFlow logic remains in `MemoryGate`, `MemoryStore`, `ReplayEngine`, `Judge`, and `ReflectionManager`.

## System Flow

```text
User Input
-> MemoryGate
-> ReplayEngine
-> Gemini ResponseGenerator
-> Judge
-> Reflection
-> Streamlit UI
```

The implementation also includes intent analysis, token/context monitoring, retrieval scoring, memory lifecycle updates, conflict handling, retry policy, and evaluation utilities.

## Current Implementation

- Streamlit web demo in `app.py`
- Gemini API integration through `google-genai`
- API key loading from `.env` through `python-dotenv`
- Default Gemini model: `gemini-2.5-flash-lite`
- JSON-backed memory store in `data/memory.json`
- Fact, summary, interaction, and reflection memory
- Memory gate that decides when retrieval should run
- Smart replay with retrieval scoring
- Judge and retry loop for response quality checks
- Reflection memory after memory-aware turns
- Demo-safe fallback when Gemini is unavailable or rate limited

If Gemini returns HTTP 429 for quota or rate limits, MemoryFlow still runs the gate, replay, judge, reflection, and storage pipeline. The app returns a demo-safe fallback message instead of crashing.

## Setup

Install dependencies:

```powershell
pip install -r requirements.txt
```

Create a local `.env` file:

```text
GEMINI_API_KEY=your_api_key
GEMINI_MODEL=gemini-2.5-flash-lite
```

`GEMINI_MODEL` is optional. If it is not set, `ResponseGenerator` uses `gemini-2.5-flash-lite`.

Do not commit `.env`, `__pycache__/`, or `*.pyc` files.

## Run Streamlit Demo

```powershell
python -m streamlit run app.py
```

The Streamlit app is the primary demo surface. It shows:

- Chat interaction
- Memory Gate status
- Retrieved memories
- Retrieval scores
- Judge result
- Reflection summary
- Memory visualization
- Agent trace

## CLI Demo

The console entrypoint still exists:

```powershell
python src/main.py
```

Supported console commands:

```text
demo
eval
stats
show memory
exit
quit
```

The Streamlit app is recommended for final presentation and submission, but the CLI remains useful for quick local checks.

## Memory Gate

MemoryFlow does not use memory for every message. `MemoryGate` checks the intent and input before retrieval.

Memory retrieval is enabled for:

- `ask_name`
- `ask_project`
- `ask_capstone`
- `ask_preference`
- `ask_summary`
- `remember_fact`

Memory retrieval is skipped for general chat, coding questions, shell commands, Git commands, and technical questions. When memory is skipped, `ReplayEngine` and `ReflectionManager` are not run for that turn, and `Judge` does not grade memory usage.

## Memory Types

Fact memory example:

```json
{
  "type": "fact",
  "key": "name",
  "value": "현우",
  "text": "사용자 이름은 현우이다.",
  "importance": 10,
  "status": "protected",
  "access_count": 1
}
```

Summary memory example:

```json
{
  "type": "summary",
  "key": "conversation_summary",
  "text": "사용자는 MemoryFlow AI 프로젝트에 대해 대화했다.",
  "importance": 7
}
```

Interaction memory example:

```json
{
  "type": "interaction",
  "user_input": "내 이름이 뭐야?",
  "ai_response": "현우님으로 기억하고 있습니다.",
  "importance": 1
}
```

## Lifecycle And Conflict Handling

All memories include lifecycle metadata:

- `created_at`
- `updated_at`
- `last_accessed`
- `access_count`
- `status`

Important memory is protected:

- `name` and `capstone_topic` are protected.
- Memory with `importance >= 8` is protected.
- Replayed memory updates `access_count` and `last_accessed`.
- If the same fact key receives a new value, `ConflictResolver` keeps the latest value and stores older values in `history`.

## Gemini Fallback Behavior

`ResponseGenerator` calls Gemini after MemoryFlow has prepared the intent, gate result, and replay memory context.

If Gemini fails:

- The exception type, status code, message, and model are printed for debugging.
- If the status code is HTTP 429, the app reports that Gemini free quota or rate limit was exceeded.
- MemoryFlow still completes its normal pipeline and saves the interaction.

## Syntax Check

```powershell
python -m py_compile app.py
python -m py_compile src/response_generator.py
```
