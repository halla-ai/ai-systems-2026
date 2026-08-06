import pytest

from calculator import divide


def test_divide_returns_quotient() -> None:
    assert divide(8, 2) == 4


def test_divide_raises_clear_error_message() -> None:
    with pytest.raises(ZeroDivisionError, match="division by zero is not allowed"):
        divide(5, 0)

