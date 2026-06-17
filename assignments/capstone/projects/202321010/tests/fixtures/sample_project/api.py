"""Sample API with intentional drift for testing."""


def parse_json(data: str) -> list:
    """Parse JSON data.

    Args:
        data (str): JSON string.

    Returns:
        dict: Parsed data.
    """
    return []


def greet(name: str, loud: bool = True) -> str:
    """Greet someone.

    Args:
        name (str): Person name.
        loud (bool): Whether to shout.

    Returns:
        str: Greeting.
    """
    return name.upper() if loud else name


def fetch_items(limit: int) -> dict:
    """Fetch items.

    Args:
        limit (int): Max items.

    Returns:
        list[dict]: Item list.
    """
    return {"items": []}
