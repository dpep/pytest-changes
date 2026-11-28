from __future__ import annotations

import copy
from typing import Any


class Incomparable(TypeError):
    """`==` returned something without a truth value, such as a numpy array."""


def equal(expected: Any, actual: Any) -> bool:
    result = expected == actual
    try:
        return bool(result)
    except Exception:  # noqa: BLE001 - __bool__ is arbitrary user code
        raise Incomparable from None


def snapshot(value: Any) -> tuple[Any, bool]:
    """A copy of `value` that later in-place mutation can't reach, and whether it is complete.

    Complete means deepcopy worked and its result is `value` itself or equals it; otherwise
    the comparison may not see inside `value` (identity equality, an uncopyable part).
    """
    try:
        deep = copy.deepcopy(value)
    except Exception:  # noqa: BLE001, S110 - copying runs arbitrary user code
        pass
    else:
        if deep is value or equal(deep, value):
            return deep, True
    try:
        shallow = copy.copy(value)
    except Exception:  # noqa: BLE001
        return value, False
    return (shallow if equal(shallow, value) else value), False
