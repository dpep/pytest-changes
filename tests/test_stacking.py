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
        "  ✗ cart.total   expected → 20, got 0 → 15\n"
        "  ✗ audit.count  expected no change, got 4 → 5"
    )
    assert len(e.value.failures) == 2


class TestBlockRaises:
    """Every context still checks when the block raises."""

    def test_every_failure_merges(self):
        cart, audit = Cart(), Audit()
        with (
            pytest.raises(ChangeAssertionError) as e,
            changes(cart, "total", by=20),
            unchanged(audit, "count"),
            unchanged(lambda: len(cart.items)),
        ):
            audit.count += 1
            cart.items.append("x")
            raise ValueError("boom")
        assert str(e.value) == (
            "3 change expectations failed\n"
            "  ✗ cart.total       expected Δ +20, did not change (stayed 0)\n"
            "  ✗ audit.count      expected no change, got 4 → 5\n"
            "  ✗ len(cart.items)  expected no change, got 0 → 1"
        )
        assert isinstance(e.value.__cause__, ValueError)

    def test_outer_contexts_still_check_after_inner_passes(self):
        cart, audit = Cart(), Audit()
        with (
            pytest.raises(ChangeAssertionError) as e,
            unchanged(audit, "count"),
            unchanged(cart, "total"),
            changes(cart, "items"),
        ):
            audit.count += 1
            cart.items.append("x")
            raise ValueError("boom")
        assert str(e.value) == "audit.count: expected no change, got 4 → 5"
        assert isinstance(e.value.__cause__, ValueError)

    def test_nested_failures_on_a_raise_merge(self):
        audit = Audit()
        # nested inside the block rather than stacked
        with pytest.raises(ChangeAssertionError) as e, changes(audit, "count", by=5):  # noqa: SIM117
            with unchanged(audit, "count"):
                audit.count += 1
                raise ValueError("boom")
        assert str(e.value) == (
            "2 change expectations failed\n"
            "  ✗ audit.count  expected Δ +5, got Δ +1 (4 → 5)\n"
            "  ✗ audit.count  expected no change, got 4 → 5"
        )
        assert isinstance(e.value.__cause__, ValueError)
