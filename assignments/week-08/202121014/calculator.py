"""Lab 04 style calculator module used as the planner analysis target."""

from __future__ import annotations


def add(a: float, b: float) -> float:
    return a + b


def divide(a: float, b: float) -> float:
    return a / b


def fibonacci(n: int) -> list[int]:
    if n <= 0:
        return []
    sequence = [0]
    while len(sequence) < n:
        if len(sequence) == 1:
            sequence.append(1)
        else:
            sequence.append(sequence[-1] + sequence[-2])
    return sequence[:n]


class Calculator:
    def divide(self, a: float, b: float) -> float:
        return divide(a, b)

