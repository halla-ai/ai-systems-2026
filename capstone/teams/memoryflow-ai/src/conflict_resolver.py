"""Conflict resolution for structured fact memory."""


class ConflictResolver:
    """Resolve fact conflicts by selecting the latest value and keeping history."""

    def resolve(self, existing_memory, new_memory):
        """Return updated memory and conflict event when values differ."""
        if not existing_memory:
            return new_memory, None

        old_value = existing_memory.get("value")
        new_value = new_memory.get("value")
        if old_value == new_value:
            merged = dict(existing_memory)
            merged.update(new_memory)
            merged["history"] = existing_memory.get("history", [])
            merged["conflict_count"] = int(existing_memory.get("conflict_count", 0))
            return merged, None

        history = list(existing_memory.get("history", []))
        if old_value and old_value not in history:
            history.append(old_value)

        resolved = dict(existing_memory)
        resolved.update(new_memory)
        resolved["history"] = history
        resolved["conflict_count"] = int(existing_memory.get("conflict_count", 0)) + 1
        event = {
            "key": new_memory.get("key"),
            "old_value": old_value,
            "new_value": new_value,
            "resolution": "latest_value_selected",
        }
        return resolved, event

    def format_conflict(self, event):
        """Format a conflict event for console output."""
        if not event:
            return ""
        return (
            "[MEMORY CONFLICT]\n"
            f"key: {event['key']}\n"
            f"old value: {event['old_value']}\n"
            f"new value: {event['new_value']}\n"
            f"resolution: {event['resolution']}"
        )
