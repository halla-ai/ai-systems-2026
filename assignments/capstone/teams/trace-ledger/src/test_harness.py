from core.harness import Harness, EventStore
import json

event_store = EventStore(".events.jsonl")
harness = Harness(event_store)
with open('logs/user_input_history.jsonl', 'r') as f:
    text = f.read()

task = {
    "task_id": "test",
    "objective": "test",
    "scope": {
        "files": ["logs/user_input_history.jsonl", "docs/runbooks/interactive_result.md"],
        "raw_text": text
    },
    "allowed_tools": [],
    "acceptance": [],
    "budget": {"max_turns": 3, "max_tokens": 100000}
}
harness.execute(task)
