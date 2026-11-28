# Changelog

## Unreleased
- `changes` and `unchanged` context managers. Pass a getter, or an object and attribute name; both are positional-only. Constrain a change with `to` or `by`, which can't be combined.
- For lists, tuples, sets and dicts, Δ counts items: `changes(lambda: lib.books, by=1)` passes when one book was added, and failures show the lengths: `expected Δ +1, got Δ +2 (len 3 → 5)`. Everything else, including types with their own `-` such as a `Counter` or a vector, is compared with `after - before`. `by` and `c.delta` follow the same rule. Strings raise `TypeError` rather than counting characters: return `int(...)` or `len(...)` from the getter.
- `by=range(1, 4)` passes when the delta is 1, 2 or 3; like `in`, the stop is excluded. Failures read `expected Δ in 1..3, got Δ +4 (0 → 4)`. An empty range raises `ValueError`, and a delta that isn't an integer (a float, a `Decimal`) raises `TypeError`: assert on `c.delta` instead.
- `c.before`, `c.after` and `c.delta` expose the values. `c.delta` counts items or subtracts by the same rule as `by`, and raises `TypeError` when the values don't subtract. `c.after` raises `AttributeError` until the block exits, or if the block raised.
- If the block raises, the check is skipped and the exception propagates untouched. To check an error path, put the expectation outside `pytest.raises`: `with unchanged(lambda: acct.balance), pytest.raises(InsufficientFunds):`.
- A `changes(...)` or `unchanged(...)` can be reused one `with` block at a time, so a list of expectations works with `parametrize`: entering one that is already in a block raises `RuntimeError`, and a block that wasn't checked is still reported even if a later block passes.
- Stacked contexts in one `with` report every failed expectation in a single error.
- The value is snapshotted before the block, so a list or dict mutated in place counts as a change. A live view (`d.keys()`, `d.values()`, `d.items()`, a `mappingproxy`) raises `TypeError` on entry: return `list(...)` or `dict(...)`.
- Without `to=` or `by=`, when the value can't be fully copied (an object without `__eq__`, a container of them, or one holding something uncopyable such as a lock), a pass emits a `pytest_changes.ChangeWarning` and a failure adds the same hint: write a getter for the state you mean, such as `lambda: vars(user)`.
- When a test returns, each `changes(...)` or `unchanged(...)` made during it (fixtures and `unittest` `setUp` included) that didn't run its check emits a `ChangeWarning` (a `RuntimeWarning`) at the call: one never used in a `with` says to use it in one, and one skipped because the block raised says to put it outside `pytest.raises`. A failing test stays quiet. Under `-W error::pytest_changes.ChangeWarning` the test fails.
- Values whose `==` doesn't return a bool, such as numpy arrays, raise `TypeError` naming the culprit, the getter's value or `to=`: return a comparable value, such as `lambda: a.tolist()`. In a stacked `with`, the other contexts' failures stay attached as its cause.
- Failures name the expression as written in the test: `changes(self.cart, "total")` reads `self.cart.total`, `changes(lambda: len(cart.items))` reads `len(cart.items)` and `changes(total)` reads `total()`. Where the source can't be read (such as code run with `exec`), labels fall back to `<Cart>.total` or `<lambda at test_cart.py:12>`. Pass `label=` to name an expectation yourself.
- Failures on long values (lists, dicts, sets, dataclasses, long strings) include pytest's assertion explanation, honouring `-v`/`-vv`, and the headline shortens those values. Outside a pytest run, messages stay on one line.
- Numeric deltas are signed (`Δ +5`, `Δ +0.50`); any other delta shows its repr.
- Requires pytest 8.4+.

## 0.0.1 (2026-11-27)
- Placeholder release to reserve the name on PyPI.
