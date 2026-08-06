"""Memory lifecycle management for MemoryFlow AI."""

from datetime import datetime


class MemoryLifecycleManager:
    """Apply lifecycle status and access metadata rules to memories."""

    PROTECTED_KEYS = {"name", "capstone_topic"}

    def apply_lifecycle_rules(self, memories):
        """Apply protection and archival rules to a memory list."""
        self.protect_important_memories(memories)
        self.archive_low_importance_memories(memories)
        return memories

    def protect_important_memories(self, memories):
        """Mark high-value memories as protected."""
        protected_count = 0
        for memory in memories:
            key = memory.get("key")
            importance = int(memory.get("importance", 1))
            access_count = int(memory.get("access_count", 0))

            if key in self.PROTECTED_KEYS or importance >= 8 or access_count >= 3:
                memory["status"] = "protected"
                protected_count += 1
            elif not memory.get("status"):
                memory["status"] = "active"
        return protected_count

    def archive_low_importance_memories(self, memories):
        """Archive low-importance interactions when they become old enough."""
        archived_count = 0
        interactions = [memory for memory in memories if memory.get("type") == "interaction"]
        old_interactions = interactions[:-20]

        for memory in old_interactions:
            if int(memory.get("importance", 1)) <= 1 and int(memory.get("access_count", 0)) == 0:
                memory["status"] = "archived"
                archived_count += 1

        return archived_count

    def update_access_metadata(self, memory):
        """Update metadata when a memory is replayed."""
        memory["access_count"] = int(memory.get("access_count", 0)) + 1
        memory["last_accessed"] = datetime.now().isoformat(timespec="seconds")
        if int(memory.get("access_count", 0)) >= 3 or int(memory.get("importance", 1)) >= 8:
            memory["status"] = "protected"
        return memory

    def ensure_metadata(self, memory):
        """Fill lifecycle metadata for older or newly created memory objects."""
        now = datetime.now().isoformat(timespec="seconds")
        memory.setdefault("created_at", memory.get("timestamp", now))
        memory.setdefault("updated_at", memory.get("timestamp", now))
        memory.setdefault("last_accessed", None)
        memory.setdefault("access_count", 0)
        memory.setdefault("status", self._initial_status(memory))
        memory.setdefault("history", [])
        memory.setdefault("conflict_count", 0)
        return memory

    def _initial_status(self, memory):
        """Return initial lifecycle status for a memory object."""
        if memory.get("key") in self.PROTECTED_KEYS:
            return "protected"
        if int(memory.get("importance", 1)) >= 8:
            return "protected"
        return "active"
