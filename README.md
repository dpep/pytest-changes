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


### Install
```
pip install pytest-changes
```

Requires Python 3.11+ and pytest 8.4+.


### Usage
Pass a zero-argument getter. With no constraint, the value just has to change:
```python
with changes(lambda: len(cart.items)):
    cart.add(item)
```

For an attribute, pass the object and the attribute name as a shorthand:
```python
with changes(cart, "total", by=20):
    cart.add(item)
```

Constrain the change with `to` (the end value, which must differ from the start) or `by` (`after - before`). They can't be combined:
```python
changes(user, "status", to="active")
changes(cart, "total", by=20)
```

Values compare with `==`, expected value first, so matchers work:
```python
changes(account, "balance", by=pytest.approx(0.1))
```

For a bound, check the delta after the block:
```python
with changes(lambda: len(queue)) as c:
    queue.push_many(jobs)
assert c.delta >= 1
```

`c.before` and `c.after` hold the values read on entering and leaving the block, and `c.delta` is `after - before`. It raises `TypeError` when they can't be subtracted.

#### Unchanged
Assert that nothing changed:
```python
from pytest_changes import unchanged

with unchanged(audit, "count"):
    audit.read()
```

`by=0` raises `TypeError`: use `unchanged()` instead.

`unchanged` checks even when the block raises. Pair it with `pytest.raises` to catch an operation that fails but still leaves a mess:
```python
with pytest.raises(ValueError), unchanged(lambda: account.balance):
    account.withdraw(500)
```
```
E       pytest_changes.ChangeAssertionError: account.balance: expected no change, got 100 → -400 (Δ -500)
```

`changes` skips its check when the block raises, since the operation didn't finish.

#### Stacking
Stack expectations in one `with`, and every failure is reported:
```python
with (
    changes(cart, "total", by=20),
    changes(lambda: len(cart.items), by=1),
    unchanged(audit, "count"),
):
    cart.add(item)
```
```
E       pytest_changes.ChangeAssertionError: 2 change expectations failed
E         ✗ cart.total   expected Δ +20, got Δ +15 (0 → 15)
E         ✗ audit.count  expected no change, got 4 → 5 (Δ +1)
```

Failures name the expression as you wrote it. Pass `label=` to name it yourself:
```python
changes(lambda: cart.total, by=20, label="cart total")
```

Values too long to read on one line get pytest's own diff, as if you'd written `assert after == expected`, and `-v`/`-vv` show more.

#### Snapshots
The value is copied before the block, so mutating it in place counts as a change:
```python
with changes(cart, "items"):
    cart.items.append(item)
```

Objects without `__eq__` compare by identity, so changing their attributes isn't a change. Write a getter for the state you mean, and a `ChangeWarning` flags results that may rest on identity:
```python
changes(lambda: vars(account))
changes(lambda: account.balance)
changes(lambda: id(account))  # if identity really is what you mean
```

The same goes for ORM models whose `==` compares primary keys: read the field, as in `changes(lambda: User.objects.get(pk=1).status)`. Values whose `==` doesn't return a bool, such as numpy arrays, raise `TypeError`: return a comparable value, as in `changes(lambda: a.tolist())`.

A `changes()` or `unchanged()` never used in a `with` asserts nothing, so it also emits a `ChangeWarning`.

For async code, use a plain `with` around the `await`:
```python
with changes(lambda: cart.total, by=15):
    await cart.add_async(item)
```

Inspired by RSpec's [`change`](https://rspec.info/features/3-13/rspec-expectations/built-in-matchers/change) matcher.

----
[![installs](https://img.shields.io/pypi/dm/pytest-changes?label=installs)](https://pypi.org/project/pytest-changes)
