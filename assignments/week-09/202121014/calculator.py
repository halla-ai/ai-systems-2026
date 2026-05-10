"""Sample target module used by the QA pipeline."""


def divide(a: float, b: float) -> float:
    """Return the quotient after validating numeric inputs."""
    if not isinstance(a, (int, float)) or not isinstance(b, (int, float)):
        raise TypeError("divide() expects numeric inputs")
    if b == 0:
        raise ZeroDivisionError("division by zero is not allowed")
    return a / b
