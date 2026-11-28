# Changelog

## Unreleased
- `changes` and `unchanged` context managers. Pass a getter, or an object and attribute name; both are positional-only. Constrain a change with `to` or `by`, which can't be combined.
- `by` and `c.delta` count items for anything with a length (lists, sets, dicts, strings), and subtract otherwise: `changes(lambda: lib.books, by=1)` passes when one book was added. Failures show the lengths: `expected Δ +1, got Δ +2 (len 3 → 5)`.
- `by=range(1, 4)` passes when the delta is 1, 2 or 3; like `in`, the stop is excluded. Failures read `expected Δ in 1..3, got Δ +4 (0 → 4)`. An empty range raises `ValueError`.
- `by=0`, or a matcher equal to 0 such as `pytest.approx(0)`, raises `TypeError`: use `unchanged()`.
- `c.before`, `c.after` and `c.delta` expose the values. `c.delta` raises `TypeError` for values that have no length and can't be subtracted. `c.after` raises `AttributeError` until the block exits.
- If the block raises, the check is skipped and the exception propagates untouched, with a `ChangeWarning` that the expectation wasn't checked (`pytest.skip`, `pytest.fail` and `KeyboardInterrupt` stay silent). To check an error path, put the expectation outside `pytest.raises`: `with unchanged(lambda: acct.balance), pytest.raises(InsufficientFunds):`.
- Stacked contexts in one `with` report every failed expectation in a single error.
- The value is snapshotted before the block, so a list or dict mutated in place counts as a change.
- Without `to=` or `by=`, when the value can't be fully copied (an object without `__eq__`, a container of them, or one holding something uncopyable such as a lock), a pass emits a `pytest_changes.ChangeWarning` and a failure adds the same hint: write a getter for the state you mean, such as `lambda: vars(user)`.
- When a test returns, each `changes(...)` or `unchanged(...)` it made but never used in a `with` emits a `ChangeWarning` (a `RuntimeWarning`) at the call, since it asserts nothing; under `-W error::pytest_changes.ChangeWarning` the test fails.
- Values whose `==` doesn't return a bool, such as numpy arrays, raise `TypeError` naming the culprit, the getter's value or `to=`: return a comparable value, such as `lambda: a.tolist()`. In a stacked `with`, the other contexts' failures stay attached as its cause.
- Failures name the expression as written in the test: `changes(self.cart, "total")` reads `self.cart.total`, `changes(lambda: len(cart.items))` reads `len(cart.items)` and `changes(total)` reads `total()`. Where the source can't be read (such as code run with `exec`), labels fall back to `<Cart>.total` or `<lambda at test_cart.py:12>`. Pass `label=` to name an expectation yourself.
- Failures on long values (lists, dicts, sets, dataclasses, long strings) include pytest's assertion explanation, honouring `-v`/`-vv`, and the headline shortens those values. Outside a pytest run, messages stay on one line.
- Deltas read as amounts: `Δ +5`, `Δ +0.50`, `Δ 1:00:00`.
- Requires pytest 8.4+.

## 0.0.1 (2026-11-27)
- Placeholder release to reserve the name on PyPI.
