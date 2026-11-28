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


class TestBlockRaises:
    """unchanged checks when the block raises; changes skips, since the block didn't finish."""

    def test_unchanged_failures_merge_and_changes_skips(self):
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
            "2 change expectations failed\n"
            "  ✗ audit.count      expected no change, got 4 → 5 (Δ +1)\n"
            "  ✗ len(cart.items)  expected no change, got 0 → 1 (Δ +1)"
        )
        assert isinstance(e.value.__cause__, ValueError)

    def test_outer_unchanged_still_checks_after_inner_passes(self):
        cart, audit = Cart(), Audit()
        with (
            pytest.raises(ChangeAssertionError) as e,
            unchanged(audit, "count"),
            unchanged(cart, "total"),
            changes(cart, "items"),
        ):
            audit.count += 1
            raise ValueError("boom")
        assert str(e.value) == "audit.count: expected no change, got 4 → 5 (Δ +1)"
        assert isinstance(e.value.__cause__, ValueError)

    def test_changes_skips_when_a_nested_unchanged_failed_on_a_raise(self):
        audit = Audit()
        # nested inside the block rather than stacked
        with pytest.raises(ChangeAssertionError) as e, changes(audit, "count", by=5):  # noqa: SIM117
            with unchanged(audit, "count"):
                audit.count += 1
                raise ValueError("boom")
        assert str(e.value) == "audit.count: expected no change, got 4 → 5 (Δ +1)"
