import pytest

from pytest_changes import ChangeAssertionError, changes, unchanged


class Cart:
    def __init__(self):
        self.total = 0
        self.items = []


class Audit:
    def __init__(self):
        self.count = 4


def test_all_pass():
    cart = Cart()
    with changes(cart, "total", by=20), changes(lambda: len(cart.items), by=1):
        cart.total += 20
        cart.items.append("x")


def test_reports_every_failure_in_source_order():
    cart, audit = Cart(), Audit()
    with (
        pytest.raises(ChangeAssertionError) as e,
        changes(cart, "total", to=20, label="cart.total"),
        changes(lambda: len(cart.items), by=1, label="len(cart.items)"),
        unchanged(audit, "count", label="audit.count"),
    ):
        cart.total = 15
        cart.items.append("x")
        audit.count += 1

    assert str(e.value) == (
        "2 change expectations failed\n"
        "  ✗ cart.total   expected → 20, got 0 → 15 (Δ +15)\n"
        "  ✗ audit.count  expected no change, got 4 → 5 (Δ +1)"
    )
    assert len(e.value.failures) == 2
