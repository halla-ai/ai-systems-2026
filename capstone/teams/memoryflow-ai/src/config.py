"""Central configuration for MemoryFlow AI.

All runtime constants are collected here so each module can share the same
limits and file locations without duplicating literal values.
"""

# Estimated token budget for the active conversation context.
TOKEN_LIMIT = 200

# Maximum number of response regeneration attempts after judge failure.
MAX_RETRIES = 2

# JSON file used by MemoryStore for long-term interaction memory.
MEMORY_FILE = "data/memory.json"

# JSON file used by ContextManager for compressed conversation context.
COMPRESSED_CONTEXT_FILE = "data/compressed_context.json"
