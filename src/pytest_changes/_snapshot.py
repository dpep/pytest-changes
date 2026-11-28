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


def snapshot(value: Any) -> Any:
    """A copy of `value` that later in-place mutation can't reach, or `value` itself."""
    for make_copy in (copy.deepcopy, copy.copy):
        try:
            candidate = make_copy(value)
            # a copy that doesn't equal the original (e.g. it holds objects with
            # identity equality) would report a change that never happened
            if equal(candidate, value):
                return candidate
        except Incomparable:
            raise
        except Exception:  # noqa: BLE001, S112 - copy and __eq__ run arbitrary user code
            continue
    return value
