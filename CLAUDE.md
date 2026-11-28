# pytest-changes

Assert that a block of code changes a value: `changes` / `unchanged` context managers.
Design brief: [Build brief: Python change-block assertions](https://claude.ai/artifact/D41uJUE6VB6CxKTnz2ZBLE)

## Gate
`script/check.sh` runs pytest, `ruff check` and `ruff format --check`. Run it before every commit.

## Constraints
- A pytest plugin: depend on pytest and lean on its machinery (assertion diffs, traceback hiding) rather than rebuilding it.
- Failure messages are the product. Every message shape has an exact-string test, so change wording on purpose and test it.
- Compare as `expected == actual`, so matchers (`pytest.approx`, dirty-equals) run their own `__eq__`.
- On an `Exception` from the block, both `changes` and `unchanged` still check; a failed check raises `ChangeAssertionError` chained from it, and a passing check lets the original propagate. Anything else (`KeyboardInterrupt`, `pytest.skip`) skips the check.
- Stacked contexts merge their failures into one `ChangeAssertionError`.
- A passing block never reads source: labels resolve on first use.
- Library frames set `__tracebackhide__` so pytest tracebacks end at the user's `with` line.
