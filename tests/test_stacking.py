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
    @pytest.mark.filterwarnings("ignore::pytest_changes.ChangeWarning")  # unchecked by design
    def test_every_context_skips_and_the_error_propagates(self):
        cart, audit = Cart(), Audit()
        with (
            pytest.raises(ValueError),
            changes(cart, "total", by=20) as total,
            unchanged(audit, "count") as count,
        ):
            raise ValueError("boom")
        for c in (total, count):
            with pytest.raises(AttributeError, match="because the block raised"):
                c.after  # noqa: B018


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


class TestInnerWarningAsError:
    """Under `-W error`, an inner context's copy hint raises from its __exit__."""

    class NoEq:
        pass

    @pytest.mark.filterwarnings("error::pytest_changes.ChangeWarning")
    def test_outer_still_checks_and_chains_from_the_warning(self):
        cart, box = Cart(), [self.NoEq()]
        with (
            pytest.raises(ChangeAssertionError) as e,
            changes(cart, "total", by=20),
            changes(lambda: box[0]),
        ):
            cart.total += 15
            box[0] = self.NoEq()
        assert str(e.value) == "cart.total: expected Δ +20, got Δ +15 (0 → 15)"
        assert isinstance(e.value.__cause__, ChangeWarning)

    @pytest.mark.filterwarnings("error::pytest_changes.ChangeWarning")
    def test_outer_pass_lets_the_warning_through(self):
        cart, box = Cart(), [self.NoEq()]
        with (
            pytest.raises(ChangeWarning, match="couldn't fully copy NoEq"),
            changes(cart, "total", by=20),
            changes(lambda: box[0]),
        ):
            cart.total += 20
            box[0] = self.NoEq()
