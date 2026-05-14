"""A tiny hello agent for Week 01."""


def run_agent(name: str = "AI Systems 2026") -> str:
    """Return a short greeting from the agent."""
    return f"Hello, {name}! Codex CLI generated this message."


if __name__ == "__main__":
    print(run_agent())
