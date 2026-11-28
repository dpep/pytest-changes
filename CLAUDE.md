# pytest-changes

Assert value changes: `changes` / `unchanged` context managers.
Design brief: [Build brief: Python change-block assertions](https://claude.ai/artifact/D41uJUE6VB6CxKTnz2ZBLE)

## Gate
`script/check.sh` runs pytest, `ruff check` and `ruff format --check`. Run it before every commit.

## Constraints
- A pytest plugin: depend on pytest and lean on its machinery (assertion diffs, traceback hiding) rather than rebuilding it.
- Failure messages are the product. Every message shape has an exact-string test, so change wording on purpose and test it.
- Compare as `expected == actual`, so matchers (`pytest.approx`, dirty-equals) run their own `__eq__`.
- If the block raises, the check is skipped and the exception propagates untouched. When a test returns, every context made or entered from its setup through its call must have run its check; any that didn't (never entered, or skipped because the block raised) gets a `ChangeWarning` at its construction site. An inner context's `ChangeAssertionError` or `ChangeWarning` isn't the block raising: outer contexts check, merging into the error or chaining from the warning.
- Every rule fits in one sentence with no exceptions. A fix that needs an exception is the wrong fix.
- Stacked contexts merge their failures into one `ChangeAssertionError`.
- A passing block never reads source: labels resolve on first use.
- Library frames set `__tracebackhide__` so pytest tracebacks end at the user's `with` line.
