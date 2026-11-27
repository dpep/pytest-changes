pytest-changes
======
Assert that a block of code changes a value.

```python
from pytest_changes import changes

with changes(cart, "total", to=20):
    cart.add(item)
```
```
AssertionError: <Cart>.total: expected → 20, got 0 → 15 (Δ +15)
```


### Install
```
pip install pytest-changes
```

Requires Python 3.11+ and pytest 8.4+.


### Usage
Pass an object and attribute name, or a zero-argument getter. With no constraint, the value just has to change:
```python
changes(cart, "total")
changes(lambda: len(queue))
```

Constraints are keyword arguments:
```python
changes(user, "status", to="active")  # end value; must also change
changes(queue, "size", by=1)  # after - before
changes(queue, "size", by_at_least=1)
changes(queue, "size", by_at_most=3)
```

`to` can't combine with `by*`.

Values compare with `==`, expected value first, so matchers work:
```python
changes(account, "balance", by=pytest.approx(0.1))
```

Assert nothing changed:
```python
from pytest_changes import unchanged

with unchanged(audit, "count"):
    audit.read()
```

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
AssertionError: 2 change expectations failed
  ✗ <Cart>.total   expected Δ +20, got Δ +15 (0 → 15)
  ✗ <Audit>.count  expected no change, got 4 → 5 (Δ +1)
```

Inspect the values afterward:
```python
with changes(cart, "items") as c:
    cart.add(item)
assert c.after[-1] is item  # also c.before, c.delta
```

#### Snapshots
The value is copied before the block, so mutating it in place counts as a change:
```python
with changes(cart, "items"):
    cart.items.append(item)
```

Objects without `__eq__` compare by identity, so changing their attributes isn't a change. Write a getter for the state you mean:
```python
changes(lambda: vars(user))
changes(lambda: user.status)
```

Only the values before and after the block are compared. An exception raised inside the block propagates unchanged, and nothing is checked.

Inspired by RSpec's [`change`](https://rspec.info/features/3-13/rspec-expectations/built-in-matchers/change) matcher.

----
[![installs](https://img.shields.io/pypi/dm/pytest-changes?label=installs)](https://pypi.org/project/pytest-changes)
