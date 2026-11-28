# Changelog

## Unreleased
- `changes` and `unchanged` context managers with `to` and `by` constraints; the getter (or object and attribute name) is positional-only. To bound a change, check the delta afterwards: `assert c.delta >= 1`. `by=0` raises `TypeError`: use `unchanged()`.
- `c.before`, `c.after` and `c.delta` expose the values. `c.delta` raises `TypeError` when they can't be subtracted, and `c.after` raises `AttributeError` until the block has exited (or when `changes` skipped reading it because the block raised).
- A `changes(...)` or `unchanged(...)` that is never used in a `with` statement emits `pytest_changes.ChangeWarning` (a `RuntimeWarning`) at the call, since it asserts nothing. Under `-W error` the test fails.
- Stacked contexts in one `with` report every failed expectation in a single error.
- When the block raises, `unchanged` still checks: a change fails with a `ChangeAssertionError` chained from the block's exception, and otherwise the exception propagates untouched. `changes` skips its check, since the block didn't finish. `KeyboardInterrupt`, `pytest.skip` and other non-`Exception` errors skip both.
- Requires pytest 8.4+.
- The value is snapshotted before the block, so a list or dict mutated in place counts as a change. Objects without `__eq__` still compare by identity: pass a getter such as `lambda: vars(user)` to compare their state. When a passing result may rest on identity (an `unchanged` on the same such object, or containers holding them, or a `changes` whose getter returned a fresh one each call) a `ChangeWarning` says so; a failure adds the same hint.
- Values whose `==` doesn't return a bool, such as numpy arrays, raise `TypeError`: return a comparable value from the getter, such as `lambda: a.tolist()`.
- Failures are labelled with the expression as written in the test: `changes(self.cart, "total")` reads `self.cart.total`, `changes(lambda: len(cart.items))` reads `len(cart.items)` and `changes(total)` reads `total()`. Where the source can't be read (such as code run with `exec`), labels fall back to `<Cart>.total` or `<lambda at test_cart.py:12>`. Pass `label=` to name an expectation yourself.
- Failures on long values (lists, dicts, sets, dataclasses, long strings) include pytest's assertion explanation, honouring `-v`/`-vv`, and the headline shortens those values. Values shown only for context (what stayed, and `by=`'s before → after) are always shortened. Outside a pytest run, messages stay on one line.
- Deltas read as amounts: `Δ +5`, `Δ +0.50`, `Δ 1:00:00`.

## 0.0.1 (2026-11-27)
- Placeholder release to reserve the name on PyPI.
