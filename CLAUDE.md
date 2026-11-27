# pytest-changes

Assert that a block of code changes a value: `changes` / `unchanged` context managers.
Design brief: [Build brief: Python change-block assertions](https://claude.ai/artifact/D41uJUE6VB6CxKTnz2ZBLE)

## Gate
`script/check.sh` runs pytest, `ruff check` and `ruff format --check`. Run it before every commit.

## Constraints
- Zero runtime dependencies, and never import pytest at runtime: the library must work under unittest and plain `assert`.
- Failure messages are the product. Every message shape has an exact-string test, so change wording on purpose and test it.
- Compare as `expected == actual`, so matchers (`pytest.approx`, dirty-equals) run their own `__eq__`.
- Exceptions raised inside the block propagate untouched; only a `ChangeAssertionError` from a stacked context is merged into.
- Library frames set `__tracebackhide__` so pytest tracebacks end at the user's `with` line.
