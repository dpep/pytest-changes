import pytest

from pytest_changes import ChangeAssertionError, ChangeWarning, changes, unchanged


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
        "  ✗ cart.total   expected → 20, got 0 → 15\n"
        "  ✗ audit.count  expected no change, got 4 → 5"
    )
    assert len(e.value.failures) == 2


class TestBlockRaises:
    def test_every_context_warns_and_the_error_propagates(self):
        cart, audit = Cart(), Audit()
        with (
            pytest.warns(ChangeWarning) as record,
            pytest.raises(ValueError),
            changes(cart, "total", by=20),
            unchanged(audit, "count"),
        ):
            raise ValueError("boom")
        assert [str(w.message).split(":")[0] for w in record] == ["audit.count", "cart.total"]


def test_nested_failures_merge():
    audit = Audit()
    # nested inside the block rather than stacked
    with pytest.raises(ChangeAssertionError) as e, changes(audit, "count", by=5):  # noqa: SIM117
        with unchanged(audit, "count"):
            audit.count += 1
    assert str(e.value) == (
        "2 change expectations failed\n"
        "  ✗ audit.count  expected Δ +5, got Δ +1 (4 → 5)\n"
        "  ✗ audit.count  expected no change, got 4 → 5"
    )
