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
    """A copy of `value` that later in-place mutation can't reach, or `value` itself.

    Also whether some copy came out unequal: `value` is, or holds, something that
    compares by identity, so in-place changes to it are invisible.
    """
    unequal = False
    for make_copy in (copy.deepcopy, copy.copy):
        try:
            candidate = make_copy(value)
            if equal(candidate, value):
                return candidate, unequal
            # a copy that is the original yet unequal is NaN-like, not identity
            unequal = unequal or candidate is not value
        except Incomparable:
            raise
        except Exception:  # noqa: BLE001, S112 - copy and __eq__ run arbitrary user code
            continue
    return value, unequal
