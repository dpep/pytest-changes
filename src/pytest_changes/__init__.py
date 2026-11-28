"""Assert that a block of code changes a value."""

from ._core import ChangeAssertionError, ChangeContext, changes, unchanged

__version__ = "0.0.1"

# tracebacks name the public import path, not the private module
ChangeAssertionError.__module__ = __name__
ChangeContext.__module__ = __name__

__all__ = [
    "ChangeAssertionError",
    "ChangeContext",
    "changes",
    "unchanged",
]
