# Changelog

## Unreleased
- `changes` and `unchanged` context managers. Pass a getter, or an object and attribute name; both are positional-only. Constrain a change with `to` or `by`, which can't be combined.
- For a bound, check the delta after the block: `assert c.delta >= 1`.
- `by=0` raises `TypeError`: use `unchanged()`.
- The delta is `after - before` for numbers, and `len(after) - len(before)` for anything with a length (lists, sets, dicts, strings): `changes(lambda: lib.books, by=1)` passes when one book was added. Failures show the lengths: `expected Δ +1, got Δ +2 (len 3 → 5)`.
- `c.before`, `c.after` and `c.delta` expose the values. `c.delta` follows the same rule, and raises `TypeError` for values that have no length and can't be subtracted. `c.after` raises `AttributeError` until the block exits.
- When the block raises an `Exception`, `changes` and `unchanged` still check: a failed check raises `ChangeAssertionError` chained from the block's exception, and a passing check lets that exception propagate untouched, so `with pytest.raises(LoginError), changes(lambda: user.failed_attempts, by=1):` asserts both. `KeyboardInterrupt`, `pytest.skip` and other non-`Exception` errors skip the check.
- Stacked contexts in one `with` report every failed expectation in a single error.
- The value is snapshotted before the block, so a list or dict mutated in place counts as a change.
- Objects without `__eq__` compare by identity: pass a getter such as `lambda: vars(user)` to compare their state. When a passing result may rest on identity, a `pytest_changes.ChangeWarning` says so, and a failure adds the same hint.
- A `changes(...)` or `unchanged(...)` never used in a `with` emits a `ChangeWarning` (a `RuntimeWarning`), since it asserts nothing. Under `-W error` the test fails.
- Values whose `==` doesn't return a bool, such as numpy arrays, raise `TypeError`: return a comparable value from the getter, such as `lambda: a.tolist()`.
- Failures name the expression as written in the test: `changes(self.cart, "total")` reads `self.cart.total`, `changes(lambda: len(cart.items))` reads `len(cart.items)` and `changes(total)` reads `total()`. Where the source can't be read (such as code run with `exec`), labels fall back to `<Cart>.total` or `<lambda at test_cart.py:12>`. Pass `label=` to name an expectation yourself.
- Failures on long values (lists, dicts, sets, dataclasses, long strings) include pytest's assertion explanation, honouring `-v`/`-vv`, and the headline shortens those values. Outside a pytest run, messages stay on one line.
- Deltas read as amounts: `Δ +5`, `Δ +0.50`, `Δ 1:00:00`.
- Requires pytest 8.4+.

## 0.0.1 (2026-11-27)
- Placeholder release to reserve the name on PyPI.
