pytest-changes
======
Assert that a block of code changes a value.

```python
from pytest_changes import changes

with changes(lambda: cart.total, by=20):
    cart.add(item)
```
```
E       pytest_changes.ChangeAssertionError: cart.total: expected Δ +20, got Δ +15 (0 → 15)
```

It replaces the familiar before-and-after dance:
```python
before = cart.total
cart.add(item)
assert cart.total - before == 20
```


## Install
```
pip install pytest-changes
```

Requires Python 3.11+ and pytest 8.4+.


## Usage
Pass a zero-argument getter. With no constraint, the value just has to change:
```python
with changes(lambda: cart.status):
    cart.checkout()
```

For an attribute, pass the object and the attribute name as a shorthand:
```python
with changes(cart, "total", by=20):
    cart.add(item)
```

To assert that nothing changed, use `unchanged`:
```python
from pytest_changes import unchanged

with unchanged(audit, "count"):
    audit.read()
```

## `to` and `by`
Constrain the change with `to` (the end value, which must differ from the start) or `by` (the difference). They can't be combined:
```python
changes(user, "status", to="active")
changes(cart, "total", by=20)
```

### Collections
For lists, tuples, sets and dicts, Δ counts items. A `Counter`'s Δ is the signed change in each count, as `Counter.subtract` computes it, so a decrease shows. Everything else, including types with their own `-` such as a vector, is compared with `after - before`. A string raises `TypeError` rather than counting characters, so a counter stored as `"9"` can't pass `by=1` by luck: return `int(...)` or `len(...)` from the getter.
```python
with changes(lambda: cart.items, by=1):
    cart.add(item)
```

### Matchers
Values compare with `==`, expected value first, so matchers such as `pytest.approx` or dirty-equals work as `by` and `to`:
```python
changes(account, "balance", by=pytest.approx(0.1))
```

### Ranges
For a range, pass one. Like `in`, the stop is excluded, so this passes for 1, 2 or 3 new jobs:
```python
with changes(lambda: queue, by=range(1, 4)):
    queue.push_many(jobs)
```
```
E       pytest_changes.ChangeAssertionError: queue: expected Δ in 1..3, got Δ +4 (len 0 → 4)
```

The delta must be an integer. A float or `Decimal` delta raises `TypeError`, so assert on `c.delta` instead (see [Before, after and delta](#before-after-and-delta)). The same goes for an open bound: `assert c.delta >= 1`.


## Before, after and delta
With `as c`, `c.before` and `c.after` hold the values read on entering and leaving the block:
```python
with changes(cart, "total") as c:
    cart.add(item)
assert c.delta == 15
```

`c.delta` follows the same rule as `by`: items added for lists, tuples, sets and dicts, signed counts for a `Counter`, else `after - before`. It raises `TypeError` when the values don't subtract.


## Stacking
Stack expectations in one `with`, and every failure is reported:
```python
with (
    changes(cart, "total", by=20),
    changes(cart, "items", by=1),
    unchanged(audit, "count"),
):
    cart.add(item)
```
```
E       pytest_changes.ChangeAssertionError: 2 change expectations failed
E         ✗ cart.total   expected Δ +20, got Δ +15 (0 → 15)
E         ✗ audit.count  expected no change, got 4 → 5
```


## Failure messages
Failures name the expression as you wrote it. Pass `label=` to name it yourself:
```python
changes(lambda: cart.total, by=20, label="cart total")
```

Values too long to read on one line get pytest's own diff, as if you'd written `assert after == expected`, and `-v`/`-vv` show more.


## When the block raises
If the block raises, the check is skipped and the exception propagates untouched. To check what a failed operation leaves behind, put the expectation outside `pytest.raises`:
```python
with unchanged(lambda: account.balance), pytest.raises(ValueError):
    account.withdraw(500)

with changes(lambda: len(log), by=1), pytest.raises(ValueError):
    account.withdraw(500)
```
```
E       pytest_changes.ChangeAssertionError: account.balance: expected no change, got 100 → -400
```

With `pytest.raises` on the outside instead, the expectation is never checked, and a [`ChangeWarning`](#warnings) says so when the test returns.


## What counts as a change
The value is copied before the block, so mutating it in place counts as a change:
```python
with changes(cart, "items"):
    cart.items.append(item)
```

Objects without `__eq__` compare by identity, so changing their attributes isn't a change, and a [`ChangeWarning`](#warnings) flags them. Write a getter for the state you mean:
```python
changes(lambda: vars(account))
changes(lambda: account.balance)
changes(lambda: id(account))  # if identity really is what you mean
```

### ORM models and numpy arrays
The same goes for ORM models whose `==` compares primary keys: read the field, as in `changes(lambda: User.objects.get(pk=1).status)`.

Values whose `==` doesn't return a bool, such as numpy arrays, raise `TypeError`: return a comparable value, as in `changes(lambda: a.tolist())`.


## Warnings
A `ChangeWarning` flags two things:

- **Unchecked contexts.** When a test returns, each `changes()` or `unchanged()` made or entered during it (fixtures and `setUp` included) that didn't run its check, because it was never entered or because the block or the getter raised, emits a warning at the line that made it. A reused context's unchecked block is still reported, even if a later block passes. One made at import time and never entered belongs to no test, so it can't warn.
- **Uncopyable values.** Values that can't be fully copied before the block, such as objects without `__eq__` or values holding something uncopyable, such as a lock.

A test that fails stays quiet, so the warning never hides the real failure.

Run with `-W error::pytest_changes.ChangeWarning` to turn these warnings into failures.

A context can be reused, one `with` block at a time. Entering one that is already in a block raises `RuntimeError`.


## Async
Use a plain `with` around the `await`:
```python
with changes(lambda: cart.total, by=15):
    await cart.add_async(item)
```

Inspired by RSpec's [`change`](https://rspec.info/features/3-13/rspec-expectations/built-in-matchers/change) matcher.

----
[![installs](https://img.shields.io/pypi/dm/pytest-changes?label=installs)](https://pypi.org/project/pytest-changes)
