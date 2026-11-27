# Changelog

## Unreleased
- `changes` and `unchanged` context managers with `to`, `by`, `by_at_least` and `by_at_most` constraints.
- Stacked contexts in one `with` report every failed expectation in a single error.
- Requires pytest 8.4+.
- The value is snapshotted before the block, so a list or dict mutated in place counts as a change. Objects without `__eq__` still compare by identity: pass a getter such as `lambda: vars(user)` to compare their state.
- Failures are labelled with the expression as written in the test: `changes(self.cart, "total")` reads `self.cart.total`, `changes(lambda: len(cart.items))` reads `len(cart.items)` and `changes(total)` reads `total()`. Where the source can't be read (such as code run with `exec`), labels fall back to `<Cart>.total` or `<lambda at test_cart.py:12>`. Pass `label=` to name an expectation yourself.

## 0.0.1 (2026-11-27)
- Placeholder release to reserve the name on PyPI.
