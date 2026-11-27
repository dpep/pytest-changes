# Changelog

## Unreleased
- `changes` and `unchanged` context managers with `to`, `by`, `by_at_least` and `by_at_most` constraints.
- Stacked contexts in one `with` report every failed expectation in a single error.
- Requires pytest 8.4+.
- The value is snapshotted before the block, so a list or dict mutated in place counts as a change. Objects without `__eq__` still compare by identity: pass a getter such as `lambda: vars(user)` to compare their state.

## 0.0.1 (2026-11-27)
- Placeholder release to reserve the name on PyPI.
