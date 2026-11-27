"""Assert that a block of code changes a value."""

from ._core import ChangeAssertionError, ChangeContext, changes, unchanged

__version__ = "0.0.1"

__all__ = [
    "ChangeAssertionError",
    "ChangeContext",
    "changes",
    "unchanged",
]
