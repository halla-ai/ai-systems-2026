# MemoryFlow AI Architecture

MemoryFlow AI is a Streamlit-based closed-loop memory agent. The system combines deterministic memory pipeline components with Gemini final response generation.

Gemini does not replace the memory pipeline. It only generates the final natural-language response from the user input, retrieved memories, Memory Gate result, intent analysis, and optional Judge feedback.

## Primary Pipeline

```text
User Input
-> MemoryGate
-> ReplayEngine
-> Gemini ResponseGenerator
-> Judge
-> Reflection
-> Streamlit UI
```

Supporting modules around this flow include `IntentAnalyzer`, `TokenMonitor`, `ContextManager`, `RetrievalScorer`, `RetryPolicy`, `MemoryLifecycleManager`, `ConflictResolver`, and `Evaluator`.

## Module Roles

- `IntentAnalyzer`: classifies the user input into intent, target, and keywords.
- `MemoryGate`: decides whether a turn should use long-term memory retrieval.
- `MemoryStore`: persists fact, summary, interaction, and reflection memory in JSON.
- `ReplayEngine`: asks `RetrievalScorer` to score candidate memories and returns the top replay memories.
- `ResponseGenerator`: builds the Gemini prompt and calls the Gemini API for the final user-facing response.
- `Judge`: evaluates relevance, memory usage, specificity, and response quality.
- `RetryPolicy`: retries response generation when Judge marks a response as insufficient.
- `ReflectionManager`: stores reflection memory based on Judge results.
- `ContextManager`: compresses context when token limits are exceeded and preserves important memory.
- `Evaluator`: reports recall, replay, judge, retry, and retention metrics.

## Gemini Integration

Gemini is integrated with `google-genai`.

Configuration is loaded from `.env` with `python-dotenv`:

```text
GEMINI_API_KEY=your_api_key
GEMINI_MODEL=gemini-2.5-flash-lite
```

`GEMINI_MODEL` is optional. The default model is:

```text
gemini-2.5-flash-lite
```

The Gemini prompt is built from MemoryFlow outputs. It includes:

- user input
- retrieved memories
- Memory Gate result
- intent analysis
- optional Judge result

Gemini is instructed not to take over `MemoryGate`, `ReplayEngine`, `Judge`, `ReflectionManager`, or `MemoryStore`.

## Quota And Failure Handling

If Gemini raises an exception, `ResponseGenerator` prints:

- exception type
- status code
- message
- configured model
- whether the failure is HTTP 429 quota/rate limit

If the status code is `429`, the app uses a demo-safe fallback message:

```text
Gemini free quota/rate limit exceeded, but MemoryFlow pipeline still ran.
```

The MemoryFlow pipeline still runs normally, including memory gate decisions, replay, judge evaluation, reflection, and interaction storage.

## Memory Gate

`MemoryGate.should_use_memory(intent, user_input)` runs once per turn.

Memory retrieval is enabled for:

- `ask_name`
- `ask_project`
- `ask_capstone`
- `ask_preference`
- `ask_summary`
- `remember_fact`

Memory retrieval is skipped for:

- `technical_question`
- `coding_question`
- `git_command`
- `shell_command`
- `programming_question`
- `general_chat`

The gate also rejects inputs that look like shell commands, Git commands, Python module commands, or technical questions.

When the gate is off:

- `ReplayEngine` is skipped.
- `RetrievalScorer` is skipped.
- `ReflectionManager` is skipped.
- `Judge` does not evaluate memory usage.

## Replay

`ReplayEngine` loads replay candidates from `MemoryStore` and scores them through `RetrievalScorer`.

Retrieval scoring considers:

- intent-to-key match
- target key match
- keyword overlap
- memory importance
- access count
- protected status
- recent access

For a name question such as `내 이름이 뭐야?`, a protected `name` fact is scored highest and passed into the Gemini prompt.

## Memory Lifecycle

MemoryStore supports:

- fact extraction
- fact upsert
- interaction storage
- recent interaction summary
- replay access metadata updates
- lifecycle protection and archival
- conflict resolution

Protected memories include:

- `name`
- `capstone_topic`
- facts with `importance >= 8`
- frequently replayed memory

When the same fact key receives a different value, the latest value is selected and the previous value is kept in `history`.

## Judge, Retry, And Reflection

`Judge` evaluates each generated response. For memory-enabled turns, it checks whether replay memory was used properly.

If Judge fails the response and retry budget remains, `RetryPolicy` asks `ResponseGenerator` to generate again with Judge feedback.

`ReflectionManager` can store reflection memory after memory-enabled turns so future retrieval can learn from earlier response quality checks.

## Streamlit UI

The Streamlit app in `app.py` is the primary demo surface.

It displays:

- chat transcript
- Memory Gate status and reason
- token count
- retrieved memories
- retrieval scores
- Judge score
- reflection summary
- memory table
- memory graph
- timeline
- agent trace

Run it with:

```powershell
python -m streamlit run app.py
```

## CLI

The console entrypoint remains available:

```powershell
python src/main.py
```

Supported commands:

```text
demo
eval
stats
show memory
exit
quit
```

The CLI is secondary to the Streamlit demo, but it still exercises the same core MemoryFlow components.

## Repository Hygiene

Do not commit:

- `.env`
- `__pycache__/`
- `*.pyc`
- local Streamlit runtime logs or pid files

Do not add MemoryFlow documentation under `src/content/docs/`; this project documentation belongs under `capstone/teams/memoryflow-ai`.
