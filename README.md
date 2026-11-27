pytest-changes
======
Assert that a block of code changes a value, like RSpec's `change` matcher.

```python
from pytest_changes import changes

with changes(cart, "total", from_=0, to=20):
    cart.add(item)
```
```
AssertionError: <Cart>.total: expected 0 → 20, got 0 → 15 (Δ +15)
```


### Install
```
pip install pytest-changes
```

Requires Python 3.11+. No dependencies: it raises `AssertionError`, so it works under pytest, unittest or plain scripts.


### Usage
Pass an object and attribute name, or a zero-argument getter:
```python
changes(cart, "total")
changes(lambda: len(queue))
```

Constraints are keyword arguments:
```python
changes(cart, "total", from_=0, to=20)  # exact transition
changes(user, "status", to="active")  # end value; must also change
changes(queue, "size", by=1)  # after - before
changes(queue, "size", by_at_least=1)
changes(queue, "size", by_at_most=3)
```

`to` can't combine with `by*`. A wrong `from_` raises `ChangePreconditionError` before the block runs.

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

Only the values before and after the block are compared. An exception raised inside the block propagates unchanged, and nothing is checked.

----
[![installs](https://img.shields.io/pypi/dm/pytest-changes?label=installs)](https://pypi.org/project/pytest-changes)
