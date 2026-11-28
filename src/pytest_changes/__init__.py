"""Assert value changes."""

from ._core import ChangeAssertionError, ChangeContext, ChangeWarning, changes, unchanged

__version__ = "0.1.0"

# tracebacks name the public import path, not the private module
ChangeAssertionError.__module__ = __name__
ChangeContext.__module__ = __name__
ChangeWarning.__module__ = __name__

__all__ = [
    "ChangeAssertionError",
    "ChangeContext",
    "ChangeWarning",
    "changes",
    "unchanged",
]
